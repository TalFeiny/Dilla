from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
import logging
from app.services.document_service import document_processor

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=Dict[str, Any])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload and process a document."""
    try:
        # Read file content
        content = await file.read()
        
        # Process document
        metadata = await document_processor.process_document(
            file_content=content,
            filename=file.filename
        )
        
        return {
            "document_id": metadata.id,
            "filename": metadata.filename,
            "file_type": metadata.file_type,
            "size": metadata.size,
            "status": "processing" if not metadata.processed else "completed"
        }
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=Dict[str, Any])
async def get_document(document_id: str):
    """Get document details."""
    try:
        document = await document_processor.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "id": document.id,
            "filename": document.filename,
            "file_type": document.file_type,
            "size": document.size,
            "uploaded_at": document.uploaded_at,
            "processed": document.processed,
            "analysis_results": document.analysis_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/analyze", response_model=Dict[str, Any])
async def analyze_document(document_id: str):
    """Analyze a document."""
    try:
        document = await document_processor.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Trigger analysis
        await document_processor._analyze_document(document)
        
        return {
            "document_id": document_id,
            "status": "analysis_started",
            "message": "Document analysis has been initiated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[Dict[str, Any]])
async def list_documents(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    file_type: Optional[str] = None
):
    """List all documents."""
    try:
        documents = await document_processor.list_documents(
            limit=limit,
            offset=offset,
            file_type=file_type
        )
        
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "size": doc.size,
                "uploaded_at": doc.uploaded_at,
                "processed": doc.processed
            }
            for doc in documents
        ]
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document."""
    try:
        success = await document_processor.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))