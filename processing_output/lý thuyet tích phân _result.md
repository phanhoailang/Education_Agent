7/17/25, 3:22 PM Lý thuyết Tích phân lớp 12 (hay, chi tiết)

![](_page_0_Picture_1.jpeg)

**VIỆ[C LÀM GIÁO D](https://1900.com.vn/viec-lam)ỤC…**

QUẢNG CÁO

#### **1. Định nghĩa**

Cho f là hàm số liên tục trên đoạn [a; b] Giả sử F là một nguyên hàm của f trên [a; b] Hiệu số F(b) - F(a) được gọi là tích phân từ a đến b (hay tích phân xác định trên

đoạn [a; b] của hàm số f(x) kí hiệu là  $\int f(x)dx$ .

Ta dùng kí hiệu  $F(x)\Big|_a^b = F(b) - F(a)$  để chỉ hiệu số F(b) - F(a). Vậy<br> $(x)dx = F(x)\Big|_a^b = F(b) - F(a)$  $\int_{a}^{b} f(x) dx = F(x) \Big|_{a}^{b} = F(b) - F(a)$ .

Nhận xét: Tích phân của hàm số f từ a đến b có thể kí hiệu bởi  $\int_{a}^{b} f(t) dt$  hay

 $\int_{a}^{b} f(x) dx$ . Tích phân đó chỉ phụ thuộc vào f và các cận a, b mà không phụ thuộc vào cách ghi biến số.

Ý nghĩa hình học của tích phân: Nếu hàm số f liên tục và không âm trên đoạn [a; b] thì tích phân  $\int\limits_{a}^{b} f(x)dx$ . là diện tích S của hình thang cong giới hạn bởi đồ thị

hàm số y = f(x), trục Ox và hai đường thẳng x = a, x = b. Vậy S =  $\int_{a}^{b} f(x) dx$ .

#### **2. Tính chất của tích phân**

7/17/25, 3:22 PM Lý thuyết Tích phân lớp 12 (hay, chi tiết)

$$
\mathbf{V}\left(\mathbf{H}\right) = \mathbf{H}\left(\mathbf{H}\right)
$$

[\(https://vietjack.com/\)](https://vietjack.com/)

$$
2.\int_{a}^{b} f(x) dx \overrightarrow{\text{and}} G d\sigma d\sigma.
$$

3. 
$$
\int_{a}^{b} f(x)dx + \int_{b}^{c} f(x)dx = \int_{a}^{c} f(x)dx \ (a < b < c) 4. \int_{a}^{b} k.f(x)dx = k. \int_{a}^{b} f(x)dx \ (k \in \mathbb{R})
$$

5. 
$$
\int_{a}^{b} [f(x) \pm g(x)] dx = \int_{a}^{b} f(x) dx \pm \int_{a}^{b} g(x) dx.
$$

B. Kĩ năng giải bài tập

# **1. Một số phương pháp tính tích phân**

## **I. Dạng 1: Tính tích phân theo công thức**

**Ví dụ 1:** Tính các tính phân sau:

a) 
$$
I = \int_{0}^{1} \frac{dx}{(1+x)^3}
$$
.  
b)  $I = \int_{0}^{1} \frac{x}{x+1} dx$ .  
c)  $I = \int_{0}^{1} \frac{2x+9}{x+3} dx$ .  
d)  $I = \int_{0}^{1} \frac{x}{4-x^2} dx$ .

**Lời giải:**

a) 
$$
I = \int_{0}^{1} \frac{dx}{(1+x)^{3}} = \int_{0}^{1} \frac{d(1+x)}{(1+x)^{3}} = -\frac{1}{2(1+x)^{2}} \Big|_{0}^{1} = \frac{3}{8}
$$
.  
\nb)  $I = \int_{0}^{1} \frac{x}{x+1} dx = \int_{0}^{1} \left(1 - \frac{1}{x+1}\right) dx = (x - \ln(x+1)) \Big|_{0}^{1} = 1 - \ln 2$ .  
\nc)  $I = \int_{0}^{1} \frac{2x+9}{x+3} dx = \int_{0}^{1} \left(2 + \frac{3}{x+3}\right) dx = (2x + 3\ln(x+3)) \Big|_{0}^{1} = 3 + 6\ln 2 - 3\ln 3$ .  
\nd)  $I = \int_{0}^{1} \frac{x}{4-x^{2}} dx = -\frac{1}{2} \int_{0}^{1} \frac{d(4-x^{2})}{4-x^{2}} = \ln|4-x^{2}| \Big|_{0}^{1} = \ln \frac{3}{4}$ .

QUẢNG CÁO

![](_page_2_Figure_2.jpeg)

## **II. Dạng 2: Dùng tính chất cận trung gian để tính tích phân**

Sử dụng tính chất 
$$
\int_{a}^{b} [f(x) + g(x)]dx = \int_{a}^{b} f(x)dx + \int_{a}^{b} g(x)dx
$$
 để bỏ dấu giá

trị tuyệt đối.

**Ví dụ 2:** Tính tích phân 
$$
I = \int_{-2}^{2} |x+1| dx
$$
.

### **Lời giải:**

Nhận xét: 
$$
|x+1| = \begin{cases} x+1, & -1 \le x \le 2 \\ -x-1, & -2 \le x < -1 \end{cases}
$$
. Do đó

$$
I = \int_{-2}^{2} |x+1| \, dx = \int_{-2}^{-1} |x+1| \, dx + \int_{-1}^{2} |x+1| \, dx = -\int_{-2}^{-1} (x+1) \, dx + \int_{-1}^{2} (x+1) \, dx = -\left[ \frac{x^2}{2} + x \right]_{-2}^{-1} + \left[ \frac{x^2}{2} + x \right]_{-1}^{2} = 5.
$$

### **III. Dạng 3: Phương pháp đổi biến số**

### **1) Đổi biến số dạng 1**

Cho hàm số f liên tục trên đoạn [a; b]. Giả sử hàm số u = u(x) có đạo hàm liên tục trên đoạn [a; b] và α ≤ u(x) ≤ β. Giả sử có thể viết f(x) = g(u(x))u'(x), x ∈ [a; b] với g liên tục trên đoạn [α; β]. Khi đó, ta có

$$
I = \int_{a}^{b} f(x)dx = \int_{u(a)}^{u(b)} g(u)du.
$$
  
  
**Ví du 3:** Tính tích phân 
$$
I = \int_{0}^{\frac{\pi}{2}} \sin^2 x \cos x dx.
$$

**Lời giải:**

ANM **VIỆ[C LÀM GIÁO D](https://1900.com.vn/viec-lam)ỤC…** (httpăst/Wienstard music du = cosxdx. Đổi cận: x = 0 ⇒ u(0) = 0; x = π/2 ⇒ u(π/2) = 1

$$
\text{Khi } \vec{\sigma} \vec{\sigma} \quad I = \int_{0}^{\frac{\pi}{2}} \sin^2 x \cos x dx = \int_{0}^{1} u^2 du = \frac{1}{3} u^3 \bigg|_{0}^1 = \frac{1}{3}.
$$

#### **Dấu hiệu nhận biết và cách tính tính phân**

|                | Dấu hiệu                               | Có thể đặt                                        | Ví du                                                                                                                                           |  |
|----------------|----------------------------------------|---------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|--|
| $\mathbf{1}$   | Có $\sqrt{f(x)}$                       | $t=\sqrt{f(x)}$                                   | $I = \int_0^3 \frac{x^3 dx}{\sqrt{x+1}}$ . Đặt $t = \sqrt{x+1}$                                                                                 |  |
| 2              | $C\acute{o}$ $(ax+b)^n$                | $t = ax + b$                                      | $I = \int_0^1 x(x+1)^{2016} dx$ . Đặt $t = x-1$                                                                                                 |  |
| 3              | Có $a^{f(x)}$                          | $t = f(x)$                                        | $I=\int_0^{\frac{\pi}{4}}\frac{e^{\tan x+3}}{\cos^2 x}dx$ . Đặt $t=\tan x+3$                                                                    |  |
| $\overline{4}$ | Có $\frac{dx}{y}$ và $\ln x$           | $t = \ln x$ <i>hoặc</i> biểu thức<br>chứa $\ln x$ | $I=\int_1^e\frac{\ln x dx}{x(\ln x+1)}$ . Đặt $t=\ln x+1$                                                                                       |  |
| 5              | $C\acute{o}$ $e^x dx$                  | $t = e^x$ <i>hoặc</i> biểu thức<br>chứa $e^x$     | $I = \int_0^{\ln 2} e^{2x} \sqrt{3e^x + 1} dx$ . Đặt $t = \sqrt{3e^x + 1}$                                                                      |  |
| 6              | $\overline{\text{C}}$ ó sin <i>xdx</i> | $t = \cos x$                                      | $I = \int_{0}^{\frac{\pi}{2}} \sin^3 x \cos x dx$ . Đặt $t = \sin x$                                                                            |  |
| 7              | $\overline{\text{Co}} \cos x dx$       | $t = \sin x dx$                                   | $I = \int_0^{\pi} \frac{\sin^3 x}{2\cos x + 1} dx$ Dặt $t = 2\cos x + 1$                                                                        |  |
| 8              | Có $\frac{dx}{\cos^2 x}$               | $t = \tan x$                                      | $I = \int_0^{\frac{\pi}{4}} \frac{1}{\cos^4 x} dx = \int_0^{\frac{\pi}{4}} (1 + \tan^2 x) \frac{1}{\cos^2 x} dx$<br>$\sum_{t=1}^{n} t = \tan x$ |  |
| 9              | Có $\frac{dx}{\sin^2 x}$               | $t = \cot x$                                      | $I = \int_{\frac{\pi}{2}}^{\frac{\pi}{4}} \frac{e^{\cot x}}{1 - \cos 2x} dx = \int \frac{e^{\cos x}}{2 \sin^2 x} dx$ . Đặt $t = \cot x$         |  |

QUẢNG CÁO

# **2) Đổi biến số dạng 2**

Cho hàm số f liên tục và có đạo hàm trên đoạn [a; b]. Giả sử hàm số x = φ(t) có  $\frac{1}{2}$  **III EXE** liên tục trên đoạn [α; β]<sup>(\*)</sup> sao cho φ(奇 طâρφ?β) GHÁDvවv G.≤ φ(t) ≤ b với thਥps:@yi<del>g</del>tjggkkand6:

$$
\int_{a}^{b} f(x)dx = \int_{\alpha}^{\beta} f(\varphi(t))\varphi'(t)dt.
$$

**Một số phương pháp đổi biến:** Nếu biểu thức dưới dấu tích phân có dạng

1. 
$$
\sqrt{a^2 - x^2}
$$
: dăt  $x = |a| \sin t$ ;  $t \in \left[ -\frac{\pi}{2}; \frac{\pi}{2} \right]$   
\n2.  $\sqrt{x^2 - a^2}$ : dăt  $x = \frac{|a|}{\sin t}$ ;  $t \in \left[ -\frac{\pi}{2}; \frac{\pi}{2} \right] \setminus \{0\}$   
\n3.  $\sqrt{x^2 + a^2}$ :  $x = |a| \tan t$ ;  $t \in \left( -\frac{\pi}{2}; \frac{\pi}{2} \right)$ 

4. 
$$
\sqrt{\frac{a+x}{a-x}}
$$
hoặc  $\sqrt{\frac{a-x}{a+x}}$ : đặt  $x = a.\cos 2t$ 

**Lưu ý:** Chỉ nên sử dụng phép đặt này khi các dấu hiệu 1, 2, 3 đi với x mũ chẵn. Ví dụ, để tính tích phân  $I = \int_0^{\sqrt{3}} \frac{x^2 dx}{\sqrt{x^2 + 1}}$  thì phải đổi biến dạng 2 còn với tích phân

 $I=\int_0^{\sqrt{3}}\frac{x^3 dx}{\sqrt{x^2+1}}$  thì nên đổi biến dạng 1.

**Ví dụ 4:** Tính các tích phân sau:

a) 
$$
I = \int_0^1 \sqrt{1 - x^2} dx
$$
. b)  $I = \int_0^1 \frac{dx}{1 + x^2}$ .

a) Đặt x = sint ta có dx = costdt. Đổi cận: x = 0 ⇒ t = 0; x = 1 ⇒ t = π/2.

Vây 
$$
I = \int_{0}^{1} \sqrt{1 - x^2} dx = \int_{0}^{\frac{\pi}{2}} |\cos t| dt = \int_{0}^{\frac{\pi}{2}} \cos t dt = \sin t \Big|_{0}^{\frac{\pi}{2}} = 1.
$$

7/17/25, 3:22 PM Lý thuyết Tích phân lớp 12 (hay, chi tiết)

**Viet dack.com**  
\n(
$$
h\oplus h\oplus h\oplus h\oplus h\oplus h\oplus h\oplus h\oplus h\oplus h\oplus h
$$

$$
x = 0 \rightarrow t = 0
$$
  
where  $x = 1 \rightarrow t = \frac{\pi}{4}$ .

Vây 
$$
I = \int_0^1 \frac{dx}{1 + x^2} = \int_0^{\frac{\pi}{4}} dt = t \Big|_0^{\frac{\pi}{4}} = \frac{\pi}{4}.
$$

## **IV. Dạng 4: Phương pháp tính tích phân từng phần.**

Định lí : Nếu u = u(x) và v = v(x) là hai hàm số có đạo hàm và liên tục trên đoạn [a; b] thì

$$
\int_{a}^{b} u(x)v'(x)dx = (u(x)v(x))\Big|_{a}^{b} - \int_{a}^{b} u'(x)v(x)dx
$$
\nAny viét gon la

\n
$$
\int_{a}^{b} u dv = uv\Big|_{a}^{b} - \int_{a}^{b} v du
$$
\nCác dạng cơ bản: Giả sử cần tính

\n
$$
I = \int_{a}^{b} P(x).Q(x)dx
$$

| Dạng<br>hàm | $P(x)$ : Đa thức<br>sin(kx)<br>$Q(x)$ :<br>hay<br>cos(kx)                   | $P(x)$ : Đa thức<br>$Q(x)$ : $e^{kx}$                                                | $P(x)$ : Đa<br>thức<br>$Q(x)$ :<br>ln(ax)<br>$\ddot{}$<br>b)                      | $P(x)$ : Đa thức<br>$Q(x)$ : 1/sin <sup>2</sup> x<br>hay<br>1/cos <sup>2</sup> x |
|-------------|-----------------------------------------------------------------------------|--------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| Cách<br>đặt | * $u = P(x)$<br>* dy là Phần còn<br>lai của biểu thức<br>dưới dấu tích phân | * $u = P(x)$<br>* dy là Phần còn<br>lại của biểu thức<br>dấu<br>tích<br>dưới<br>phân | *<br>$\overline{u}$<br>$=$<br>ln(ax)<br>$\ddot{}$<br>b)<br>$\star$ dv =<br>P(x)dx | * $u = P(x)$<br>* dv là Phần còn lại<br>của biểu thức dưới<br>dấu tích phân      |

**Thông thường nên chú ý: "Nhất log, nhì đa, tam lượng, tứ mũ".**

QUẢNG CÁO

![](_page_6_Figure_2.jpeg)

**Lời giải:**

a) Đăt 
$$
\begin{cases} u = x \\ dv = \sin x dx \end{cases}
$$
ta có 
$$
\begin{cases} du = dx \\ v = -\cos x \end{cases}
$$
.

Do đó 
$$
I = \int_{0}^{\frac{\pi}{2}} x \sin x dx = (-x \cos x)|_0^{\frac{\pi}{2}} + \int_{0}^{\frac{\pi}{2}} \cos x dx = 0 + \sin x|_0^{\frac{\pi}{2}} = 1.
$$

b) Đặc 
$$
\begin{cases} u = \ln(x+1) \\ dv = x dx \end{cases}
$$
ta có 
$$
\begin{cases} du = \frac{1}{x+1} dx \\ v = \frac{x^2 - 1}{2} \end{cases}
$$

$$
I = \int_{0}^{e-1} x \ln(x+1) dx = \left[ \ln(x+1) \frac{x^2 - 1}{2} \right]_{0}^{e-1} - \frac{1}{2} \int_{0}^{e-1} (x-1) dx = \frac{e^2 - 2e + 2}{2} - \frac{1}{2} \left( \frac{x^2}{2} - x \right) \Big|_{0}^{e-1}
$$
  
=  $\frac{e^2 - 2e + 2}{2} - \frac{1}{2} \frac{e^2 - 4e + 3}{2} = \frac{e^2 + 1}{4}.$ 

Xem thêm các dạng bài tập Toán lớp 12 ôn thi Tốt nghiệp có lời giải hay khác:

**Lý thuyết Nguyên hàm** [\(../toan-lop-12/ly-thuyet-nguyen-ham.jsp\)](https://vietjack.com/toan-lop-12/ly-thuyet-nguyen-ham.jsp)

**Lý thuyết Tích phân** [\(../toan-lop-12/ly-thuyet-tich-phan.jsp\)](https://vietjack.com/toan-lop-12/ly-thuyet-tich-phan.jsp)

**Lý thuyết Ứng dụng của tích phân trong hình học** [\(../toan-lop-12/ly-thuyet-ung-dung-cua](https://vietjack.com/toan-lop-12/ly-thuyet-ung-dung-cua-tich-phan-trong-hinh-hoc.jsp)tich-phan-trong-hinh-hoc.jsp)

**Lý thuyết Ôn tập chương 3** [\(../toan-lop-12/ly-thuyet-on-tap-chuong-3.jsp\)](https://vietjack.com/toan-lop-12/ly-thuyet-on-tap-chuong-3.jsp)

HOT 500+ Đề thi thử tốt nghiệp THPT, ĐGNL các trường ĐH fle word có đáp án (2025). [\(https://tailieugiaovien.com.vn/danh-sach-tai-lieu?lop=dgnl-dgtd%2Ctot-nghiep](https://tailieugiaovien.com.vn/danh-sach-tai-lieu?lop=dgnl-dgtd%2Ctot-nghiep-thpt&q=&fbclid=fbclid)thpt&q=&fbclid=fbclid)