import os
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from utils.GPTClient import GPTClient
from agents.SlideOutlineAgent import SlideOutlineAgent


PRESENTATION_MIME = "application/vnd.google-apps.presentation"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PDF_MIME = "application/pdf"


class GoogleSlidePipeline:
    """
    Pipeline:
      1) auth Google APIs
      2) ask SlideOutlineAgent → outline (markdown)
      3) parse outline → structure
      4) create (or open) Google Slides file (optionally in folder_id)
      5) batchUpdate: tạo slide, text box, bullets, speaker notes, background
      6) (optional) export PPTX/PDF
    """
    def __init__(self, llm: GPTClient, credentials_path: Optional[str] = None):
        self.llm = llm
        self.outline_agent = SlideOutlineAgent(llm)

        # Google scopes
        self.SCOPES = [
            "https://www.googleapis.com/auth/presentations",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.token_path = "token.json"

        self.slides_service = None
        self.drive_service = None

        # Output
        self.output_dir = Path("output_slides")
        self.output_dir.mkdir(exist_ok=True)

        # palette
        self.color_schemes = {
            "blue":   {"primary": "#1e40af", "secondary": "#3b82f6", "accent": "#60a5fa"},
            "green":  {"primary": "#166534", "secondary": "#10b981", "accent": "#34d399"},
            "purple": {"primary": "#7c3aed", "secondary": "#8b5cf6", "accent": "#a78bfa"},
            "orange": {"primary": "#ea580c", "secondary": "#f59e0b", "accent": "#fbbf24"},
            "red":    {"primary": "#dc2626", "secondary": "#ef4444", "accent": "#f87171"},
            "gray":   {"primary": "#374151", "secondary": "#6b7280", "accent": "#9ca3af"},
        }

    # ---------- Auth ----------
    def authenticate(self) -> bool:
        """OAuth user-flow; lưu token.json"""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    print(f"❌ Không tìm thấy {self.credentials_path}")
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            Path(self.token_path).write_text(creds.to_json(), encoding="utf-8")

        try:
            self.slides_service = build("slides", "v1", credentials=creds)
            self.drive_service = build("drive", "v3", credentials=creds)
            print("✅ Google API authentication successful")
            return True
        except Exception as e:
            print(f"❌ Google API authentication failed: {e}")
            return False

    # ---------- Public API ----------
    def create_slide_from_lesson_plan(
        self,
        lesson_plan_content: str,
        user_requirements: str = "",
        slide_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Tạo slide từ lesson plan → Google Slides (+ HTML preview).
        slide_config:
            - folder_id: tạo file trực tiếp trong folder (đã share cho SA/OAuth user)
            - color_scheme: "blue"|"green"|...
            - supportsAllDrives: bool (nếu dùng Shared Drive)
            - subtitle: phụ đề cho title slide
            - add_share: [{"email": "...", "role": "writer|reader"}]
            - export: {"pptx": True, "pdf": False}
        """
        try:
            print("🎬 Bắt đầu tạo slide từ lesson plan...")
            cfg = slide_config or {}

            if not self.authenticate():
                return {"success": False, "error": "Không thể xác thực với Google API"}

            # 1) Outline
            slide_outline = self.outline_agent.run(lesson_plan_content, user_requirements)

            # 2) Parse outline
            slide_structure = self._parse_outline(slide_outline)

            # 3) Create empty presentation (optionally in folder)
            pres_id = self._create_empty_presentation(
                title=slide_structure.get("title", "EduMate Presentation"),
                folder_id=cfg.get("folder_id"),
                supportsAllDrives=bool(cfg.get("supportsAllDrives", False))
            )
            if not pres_id:
                return {"success": False, "error": "Không tạo được file trình chiếu"}

            # 4) Render slides
            self._render_structure_to_presentation(
                presentation_id=pres_id,
                slides_data=slide_structure.get("slides", []),
                color_scheme=cfg.get("color_scheme", "blue"),
                subtitle=cfg.get("subtitle", "")
            )

            # 5) Share (optional)
            if cfg.get("add_share"):
                self._share_file(pres_id, cfg["add_share"], cfg.get("supportsAllDrives", False))

            edit_url = f"https://docs.google.com/presentation/d/{pres_id}/edit#slide=id.p"
            present_url = f"https://docs.google.com/presentation/d/{pres_id}/present"

            # 6) HTML local preview (optional, giữ phiên bản đơn giản)
            html_result = self._generate_html_slides(slide_structure, {"color_scheme": cfg.get("color_scheme", "blue")})

            # 7) Export (optional)
            exports = {}
            if cfg.get("export", {}).get("pptx"):
                exports["pptx_path"] = self._export_local(pres_id, PPTX_MIME, "deck.pptx")
            if cfg.get("export", {}).get("pdf"):
                exports["pdf_path"] = self._export_local(pres_id, PDF_MIME, "deck.pdf")

            # 8) Save metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            outline_path = self.output_dir / f"slide_outline_{timestamp}.md"
            outline_path.write_text(slide_outline, encoding="utf-8")

            json_path = self.output_dir / f"slides_{timestamp}.json"
            data = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "slide_count": len(slide_structure.get("slides", [])),
                    "google_slides_url": present_url,
                    "edit_url": edit_url,
                    "presentation_id": pres_id,
                },
                "outline": slide_outline,
                "structure": slide_structure,
                "exports": exports,
                "html_result": html_result,
            }
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"✅ Hoàn thành: {len(slide_structure.get('slides', []))} slides → {edit_url}")
            return {
                "success": True,
                "presentation_id": pres_id,
                "google_slides_url": present_url,
                "edit_url": edit_url,
                "slide_count": len(slide_structure.get("slides", [])),
                "outline_path": str(outline_path),
                "json_path": str(json_path),
                **exports,
                "html_path": html_result.get("html_path", ""),
            }

        except Exception as e:
            msg = f"Lỗi trong pipeline tạo slide: {e}"
            print(f"❌ {msg}")
            return {"success": False, "error": msg, "slides": [], "slide_count": 0}

    # ---------- Drive/Slides helpers ----------
    def _create_empty_presentation(self, title: str, folder_id: Optional[str], supportsAllDrives: bool) -> Optional[str]:
        """
        Nếu có folder_id → tạo file trình chiếu trực tiếp trong folder qua Drive API.
        Nếu không → dùng Slides API create (tạo ở root).
        """
        try:
            if folder_id:
                meta = {"name": title, "mimeType": PRESENTATION_MIME, "parents": [folder_id]}
                file = self.drive_service.files().create(
                    body=meta, fields="id", supportsAllDrives=supportsAllDrives
                ).execute()
                return file["id"]
            else:
                pres = self.slides_service.presentations().create(body={"title": title}).execute()
                return pres["presentationId"]
        except HttpError as e:
            print(f"❌ Create presentation error: {e}")
            return None

    def _render_structure_to_presentation(self, presentation_id: str, slides_data: List[Dict[str, Any]],
                                          color_scheme: str = "blue", subtitle: str = ""):
        """
        Tạo toàn bộ slide từ đầu:
          - Xoá slide mặc định
          - Với mỗi slide: createSlide → createShape (title/body) → insertText → bullets → notes
          - Áp background cho title slide
        """
        # Lấy palette
        palette = self.color_schemes.get(color_scheme, self.color_schemes["blue"])

        # Lấy slide mặc định để xoá
        pres = self.slides_service.presentations().get(presentationId=presentation_id).execute()
        default_slides = pres.get("slides", [])
        requests: List[Dict[str, Any]] = []

        if default_slides:
            requests.append({"deleteObject": {"objectId": default_slides[0]["objectId"]}})

        # Kích thước trang mặc định: 960×540 pt
        def page_id(i): return f"page_{i+1}"
        def title_id(i): return f"title_{i+1}"
        def body_id(i): return f"body_{i+1}"

        for i, sl in enumerate(slides_data):
            # 1) create page
            requests.append({
                "createSlide": {
                    "objectId": page_id(i),
                    "slideLayoutReference": {"predefinedLayout": "BLANK"},
                    "insertionIndex": i
                }
            })

            # 2) title box
            requests.append({
                "createShape": {
                    "objectId": title_id(i),
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": page_id(i),
                        "size": {"width": {"magnitude": 820, "unit": "PT"},
                                 "height": {"magnitude": 80, "unit": "PT"}},
                        "transform": {"scaleX": 1, "scaleY": 1, "translateX": 70, "translateY": 50, "unit": "PT"},
                    },
                }
            })
            requests.append({"insertText": {"objectId": title_id(i), "insertionIndex": 0, "text": sl.get("title", f"Slide {i+1}")}})
            requests.append({
                "updateTextStyle": {
                    "objectId": title_id(i),
                    "textRange": {"type": "ALL"},
                    "style": {"fontSize": {"magnitude": 28, "unit": "PT"}, "bold": True}
                }
            })

            # 3) body box (content bullets)
            content_list = sl.get("content") or []
            if content_list:
                requests.append({
                    "createShape": {
                        "objectId": body_id(i),
                        "shapeType": "TEXT_BOX",
                        "elementProperties": {
                            "pageObjectId": page_id(i),
                            "size": {"width": {"magnitude": 760, "unit": "PT"},
                                     "height": {"magnitude": 340, "unit": "PT"}},
                            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 90, "translateY": 150, "unit": "PT"},
                        },
                    }
                })
                text = "\n".join(content_list[:6])
                requests.append({"insertText": {"objectId": body_id(i), "insertionIndex": 0, "text": text}})
                requests.append({
                    "createParagraphBullets": {
                        "objectId": body_id(i),
                        "textRange": {"type": "ALL"},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                    }
                })
                requests.append({
                    "updateTextStyle": {
                        "objectId": body_id(i),
                        "textRange": {"type": "ALL"},
                        "style": {"fontSize": {"magnitude": 18, "unit": "PT"}}
                    }
                })

            # 4) notes (speaker notes từ outline nếu có key 'notes' hoặc 'speaker_notes')
            notes_text = sl.get("notes") or sl.get("speaker_notes") or ""
            if notes_text:
                # speaker notes object id có sẵn trong notesPage
                # ta sẽ chèn sau khi slides được tạo (cần page ids tồn tại)
                pass

            # 5) title slide background
            if i == 0:
                requests.append({
                    "updatePageProperties": {
                        "objectId": page_id(i),
                        "pageProperties": {
                            "pageBackgroundFill": {
                                "solidFill": {
                                    "color": {"rgbColor": self._hex_to_rgb(palette["primary"])},
                                    "alpha": 1.0
                                }
                            }
                        },
                        "fields": "pageBackgroundFill.solidFill.color,pageBackgroundFill.solidFill.alpha"
                    }
                })
                # Subtitle nhỏ dưới title (nếu có)
                if subtitle:
                    sub_id = f"subtitle_{i+1}"
                    requests.append({
                        "createShape": {
                            "objectId": sub_id,
                            "shapeType": "TEXT_BOX",
                            "elementProperties": {
                                "pageObjectId": page_id(i),
                                "size": {"width": {"magnitude": 820, "unit": "PT"},
                                         "height": {"magnitude": 50, "unit": "PT"}},
                                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 70, "translateY": 120, "unit": "PT"},
                            },
                        }
                    })
                    requests.append({"insertText": {"objectId": sub_id, "insertionIndex": 0, "text": subtitle}})
                    requests.append({
                        "updateTextStyle": {
                            "objectId": sub_id, "textRange": {"type": "ALL"},
                            "style": {"fontSize": {"magnitude": 18, "unit": "PT"}, "bold": False}
                        }
                    })

        # Gửi batch đầu tiên (tạo pages/shapes/text)
        if requests:
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id, body={"requests": requests}
            ).execute()

        # Thêm speaker notes (cần gọi sau khi pages tồn tại)
        self._apply_notes(presentation_id, slides_data)

    def _apply_notes(self, presentation_id: str, slides_data: List[Dict[str, Any]]):
        pres = self.slides_service.presentations().get(presentationId=presentation_id).execute()
        slides = pres.get("slides", [])
        requests: List[Dict[str, Any]] = []

        for i, sl in enumerate(slides_data):
            notes_text = sl.get("notes") or sl.get("speaker_notes") or ""
            if not notes_text:
                continue
            slide = slides[i]
            notes_page = slide.get("slideProperties", {}).get("notesPage", {})
            speaker_obj = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
            if not speaker_obj:
                # fallback: tạo note box
                speaker_obj = f"notes_{i+1}"
                requests.append({
                    "createShape": {
                        "objectId": speaker_obj,
                        "shapeType": "TEXT_BOX",
                        "elementProperties": {
                            "pageObjectId": notes_page.get("objectId", slide["objectId"]),
                            "size": {"width": {"magnitude": 760, "unit": "PT"},
                                     "height": {"magnitude": 300, "unit": "PT"}},
                            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 80, "translateY": 120, "unit": "PT"},
                        },
                    }
                })
            requests.append({"insertText": {"objectId": speaker_obj, "insertionIndex": 0, "text": notes_text}})

        if requests:
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id, body={"requests": requests}
            ).execute()

    def _share_file(self, file_id: str, shares: List[Dict[str, str]], supportsAllDrives: bool):
        for s in shares:
            try:
                body = {"type": "user", "role": s.get("role", "reader"), "emailAddress": s["email"]}
                self.drive_service.permissions().create(
                    fileId=file_id, body=body, sendNotificationEmail=False,
                    supportsAllDrives=supportsAllDrives
                ).execute()
            except Exception as e:
                print(f"⚠️ Share failed for {s}: {e}")

    def _export_local(self, presentation_id: str, mime: str, filename: str) -> str:
        data = self.drive_service.files().export(fileId=presentation_id, mimeType=mime).execute()
        out_path = self.output_dir / filename
        out_path.write_bytes(data)
        return str(out_path)

    # ---------- Parsing & HTML preview ----------
    def _parse_outline(self, outline: str) -> Dict[str, Any]:
        """
        Parse outline markdown thành cấu trúc:
        {
          "title": "...",
          "slides": [{"title": "...", "type": "...", "content": ["..."] , "notes": "..."}]
        }
        """
        try:
            lines = [ln.strip() for ln in outline.splitlines() if ln.strip()]
            structure = {
                "title": "Slide Presentation",
                "subject": "",
                "grade": "",
                "slide_count": 0,
                "design_style": "modern",
                "slides": []
            }

            # Basic info
            for ln in lines:
                if ln.startswith("- **Tiêu đề bài giảng:**"):
                    structure["title"] = ln.split("**Tiêu đề bài giảng:**", 1)[-1].strip(" :-[]")
                if ln.startswith("- **Môn học:**"):
                    # "- **Môn học:** Toán - **Lớp:** 10"
                    parts = ln.split("**Môn học:**", 1)[-1].strip()
                    structure["subject"] = parts.split("- **Lớp:**")[0].strip(" :-")
                if ln.startswith("- **Tổng số slide:**"):
                    try:
                        structure["slide_count"] = int(ln.split(":")[-1].split()[0])
                    except:
                        structure["slide_count"] = 10

            current = None
            in_content = False

            for ln in lines:
                # slide header
                m = None
                if ln.startswith("### SLIDE"):
                    m = True
                else:
                    m = None
                if m and ln.startswith("### SLIDE"):
                    # Examples: "### SLIDE 2: MỤC TIÊU BÀI HỌC"
                    title = ln.replace("### SLIDE", "").strip()
                    if ":" in title:
                        title = title.split(":", 1)[1].strip()
                    if current:
                        structure["slides"].append(current)
                    current = {"title": title or f"Slide {len(structure['slides'])+1}",
                               "type": "content", "content": [], "design": {}}
                    in_content = True
                    continue

                if not current:
                    continue

                # type
                if ln.startswith("- **Loại:**"):
                    current["type"] = ln.split(":", 1)[-1].strip()

                # nội dung bullets
                if ln.startswith("+ "):
                    item = ln[2:].strip()
                    if item:
                        current["content"].append(item)

                if ln.startswith("- **Nội dung:**"):
                    # những dòng sau thường là "+ ..." — đã xử lý
                    pass

                # notes (nếu outline có)
                if ln.lower().startswith("ghi chú giảng:") or ln.lower().startswith("speaker notes:"):
                    current["notes"] = ln.split(":", 1)[-1].strip()

                # thiết kế
                if "Background:" in ln or "Layout:" in ln or "Font:" in ln:
                    key, val = ln.replace("+ ", "").split(":", 1)
                    current["design"][key.strip().lower()] = val.strip()

            if current:
                structure["slides"].append(current)

            return structure

        except Exception as e:
            print(f"⚠️ Lỗi parse outline: {e}")
            return {
                "title": "Slide Presentation",
                "slides": [{"title": "Title Slide", "content": ["Generated from lesson plan"], "type": "title"}]
            }

    def _generate_html_slides(self, structure: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Preview HTML đơn giản cho local"""
        try:
            slides = structure.get("slides", [])
            color = self.color_schemes.get(config.get("color_scheme", "blue"))
            html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"><title>{structure.get('title','EduMate Slides')}</title>
<style>
body{{margin:0;background:linear-gradient(135deg,{color['primary']},{color['secondary']});font-family:Segoe UI,Arial}}
.container{{height:100vh;display:flex;align-items:center;justify-content:center}}
.slide{{width:960px;height:540px;background:#fff;border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,.2);padding:40px;display:none}}
.slide.active{{display:block}}
h1{{margin:0 0 16px;color:{color['primary']}}}
li{{font-size:18px;line-height:1.6;margin:8px 0}}
.ctrl{{position:fixed;bottom:24px;right:24px;display:flex;gap:8px}}
.btn{{background:{color['primary']};color:#fff;border:none;border-radius:999px;padding:10px 16px;cursor:pointer}}
.counter{{position:fixed;top:24px;right:24px;background:rgba(0,0,0,.7);color:#fff;padding:6px 12px;border-radius:999px}}
</style></head><body>
<div class="container">"""
            for i, sl in enumerate(slides):
                html += f'<div class="slide{" active" if i==0 else ""}" id="s{i+1}"><h1>{sl.get("title","Slide")}</h1>'
                if sl.get("content"):
                    html += "<ul>"
                    for it in sl["content"][:6]:
                        html += f"<li>{it}</li>"
                    html += "</ul>"
                html += "</div>"
            html += f"""</div>
<div class="ctrl"><button class="btn" onclick="p()">◀ Trước</button><button class="btn" onclick="n()">Sau ▶</button></div>
<div class="counter"><span id="c">1</span> / {len(slides)}</div>
<script>
let i=1, t={len(slides)};
function sh(n){{document.querySelectorAll('.slide').forEach(e=>e.classList.remove('active'));document.getElementById('s'+i).classList.add('active');document.getElementById('c').textContent=i;}}
function n(){{i++; if(i>t) i=1; sh()}}
function p(){{i--; if(i<1) i=t; sh()}}
document.addEventListener('keydown', e=>{{if(e.key==='ArrowRight'||e.key===' ')n(); if(e.key==='ArrowLeft')p();}});
sh();
</script></body></html>"""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.output_dir / f"slides_{timestamp}.html"
            path.write_text(html, encoding="utf-8")
            return {"success": True, "html_path": str(path), "slide_count": len(slides)}
        except Exception as e:
            print(f"❌ Error generating HTML slides: {e}")
            return {"success": False, "error": str(e)}

    # ---------- Utils ----------
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Dict[str, float]:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return {"red": r, "green": g, "blue": b}


# Alias giữ tương thích
SlidePipeline = GoogleSlidePipeline
