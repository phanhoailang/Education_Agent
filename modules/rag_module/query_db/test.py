#!/usr/bin/env python3
"""
Debug embedding field trong documents
"""

import os
from pymongo import MongoClient

def debug_embedding_field():
    """Kiểm tra chi tiết field embedding trong documents"""
    
    print("🔍 DEBUG EMBEDDING FIELD")
    print("="*50)
    
    client = MongoClient(os.environ.get("MONGO_URI"))
    db = client[os.environ.get("MONGO_DB_NAME")]
    collection = db["lectures"]
    
    # 1. Kiểm tra documents có field embedding
    docs_with_embedding = collection.count_documents({"embedding": {"$exists": True}})
    docs_without_embedding = collection.count_documents({"embedding": {"$exists": False}})
    total_docs = collection.count_documents({})
    
    print(f"📊 THỐNG KÊ EMBEDDING:")
    print(f"   Total documents: {total_docs}")
    print(f"   Có embedding: {docs_with_embedding}")
    print(f"   Không có embedding: {docs_without_embedding}")
    
    # 2. Kiểm tra documents có embedding trong metadata
    docs_with_metadata_embedding = collection.count_documents({"metadata.embedding": {"$exists": True}})
    print(f"   Có metadata.embedding: {docs_with_metadata_embedding}")
    
    # 3. Lấy sample document để kiểm tra structure
    print(f"\n📋 SAMPLE DOCUMENT STRUCTURE:")
    sample_doc = collection.find_one()
    if sample_doc:
        print(f"   Document ID: {sample_doc['_id']}")
        print(f"   Fields: {list(sample_doc.keys())}")
        
        # Kiểm tra field embedding
        if 'embedding' in sample_doc:
            embedding = sample_doc['embedding']
            print(f"   ✅ Has 'embedding' field:")
            print(f"      Type: {type(embedding)}")
            if isinstance(embedding, list):
                print(f"      Length: {len(embedding)}")
                print(f"      Sample values: {embedding[:5]}")
            else:
                print(f"      Value: {embedding}")
        else:
            print(f"   ❌ NO 'embedding' field")
        
        # Kiểm tra metadata.embedding
        if 'metadata' in sample_doc and isinstance(sample_doc['metadata'], dict):
            metadata = sample_doc['metadata']
            print(f"   📦 Metadata fields: {list(metadata.keys())}")
            
            if 'embedding' in metadata:
                meta_embedding = metadata['embedding']
                print(f"   ✅ Has 'metadata.embedding':")
                print(f"      Type: {type(meta_embedding)}")
                if isinstance(meta_embedding, list):
                    print(f"      Length: {len(meta_embedding)}")
                    print(f"      Sample values: {meta_embedding[:5]}")
            else:
                print(f"   ❌ NO 'metadata.embedding'")
        else:
            print(f"   ❌ NO 'metadata' field or not dict")
    
    # 4. Tìm document có embedding (nếu có)
    print(f"\n🔍 TÌM DOCUMENTS CÓ EMBEDDING:")
    
    # Thử tìm theo field embedding
    doc_with_embedding = collection.find_one({"embedding": {"$exists": True}})
    if doc_with_embedding:
        print(f"   ✅ Found document with 'embedding' field")
        embedding = doc_with_embedding['embedding']
        print(f"      Embedding type: {type(embedding)}")
        print(f"      Embedding length: {len(embedding) if isinstance(embedding, list) else 'N/A'}")
    else:
        print(f"   ❌ No documents with 'embedding' field")
    
    # Thử tìm theo metadata.embedding
    doc_with_meta_embedding = collection.find_one({"metadata.embedding": {"$exists": True}})
    if doc_with_meta_embedding:
        print(f"   ✅ Found document with 'metadata.embedding'")
        meta_embedding = doc_with_meta_embedding['metadata']['embedding']
        print(f"      Metadata embedding type: {type(meta_embedding)}")
        print(f"      Metadata embedding length: {len(meta_embedding) if isinstance(meta_embedding, list) else 'N/A'}")
    else:
        print(f"   ❌ No documents with 'metadata.embedding'")
    
    # 5. Kiểm tra search index configuration
    print(f"\n🔧 SEARCH INDEX ANALYSIS:")
    try:
        indexes = list(collection.list_search_indexes())
        for idx in indexes:
            print(f"   Index: {idx.get('name')}")
            print(f"   Status: {idx.get('status')}")
            print(f"   Definition: {idx.get('definition', {})}")
            
            # Kiểm tra xem index đang map vào field nào
            definition = idx.get('definition', {})
            fields = definition.get('fields', [])
            for field in fields:
                if field.get('type') == 'vector':
                    vector_path = field.get('path')
                    print(f"   🎯 Vector field path: '{vector_path}'")
                    
                    # Kiểm tra xem path này có tồn tại trong documents không
                    if vector_path == 'embedding':
                        count = collection.count_documents({"embedding": {"$exists": True}})
                        print(f"      Documents with '{vector_path}': {count}")
                    elif vector_path == 'metadata.embedding':
                        count = collection.count_documents({"metadata.embedding": {"$exists": True}})
                        print(f"      Documents with '{vector_path}': {count}")
                    else:
                        # Dynamic path check
                        try:
                            count = collection.count_documents({vector_path: {"$exists": True}})
                            print(f"      Documents with '{vector_path}': {count}")
                        except:
                            print(f"      Cannot check '{vector_path}'")
    except Exception as e:
        print(f"   ❌ Error checking indexes: {e}")
    
    # 6. Đề xuất giải pháp
    print(f"\n💡 GIẢI PHÁP:")
    
    if docs_with_embedding == 0 and docs_with_metadata_embedding == 0:
        print("   🚨 VẤN ĐỀ: Không có documents nào có embedding!")
        print("   🔧 GIẢI PHÁP:")
        print("      1. Chạy migration để tạo embedding cho documents hiện có")
        print("      2. Hoặc re-process documents với embedding")
        
    elif docs_with_embedding == 0 and docs_with_metadata_embedding > 0:
        print("   🚨 VẤN ĐỀ: Embedding nằm trong metadata.embedding, không phải embedding")
        print("   🔧 GIẢI PHÁP:")
        print("      1. Migrate embedding từ metadata.embedding sang embedding")
        print("      2. Hoặc update search index để dùng 'metadata.embedding' path")
        
    elif docs_with_embedding > 0:
        print("   🚨 VẤN ĐỀ: Có embedding nhưng search không hoạt động")
        print("   🔧 GIẢI PHÁP:")
        print("      1. Kiểm tra embedding dimension compatibility")
        print("      2. Rebuild search index")
        print("      3. Kiểm tra aggregation pipeline syntax")

if __name__ == "__main__":
    debug_embedding_field()