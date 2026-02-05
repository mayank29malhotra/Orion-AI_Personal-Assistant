"""
Media Agent for Orion
=====================

Specialized sub-agent for YouTube, audio, and document processing.

Capabilities:
- YouTube video transcripts and search
- Audio transcription (Whisper)
- PDF extraction and creation
- OCR (image to text)
- CSV, Excel, JSON processing
- QR code generation
"""

from typing import List, Optional
from langchain_core.tools import tool, BaseTool

from agents.base_agent import BaseSubAgent


class MediaAgent(BaseSubAgent):
    """
    Media Agent - handles YouTube, audio, and document tasks.
    
    This agent specializes in:
    - YouTube transcript extraction
    - Video search and information
    - Audio transcription
    - PDF processing
    - OCR (optical character recognition)
    - Data file handling (CSV, Excel, JSON)
    """
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        if tools is None:
            tools = get_media_agent_tools()
        super().__init__(tools)
    
    def get_system_prompt(self) -> str:
        return """You are the Media Agent, a specialized sub-agent of Orion AI.
Your expertise is in processing YouTube content, audio, and documents.

🎯 YOUR CAPABILITIES:

📺 YOUTUBE:
- Get video transcripts (auto/manual captions)
- Search YouTube videos
- Get video information (title, duration, views)
- Support for multiple languages (English, Hindi, etc.)

🎙️ AUDIO:
- Transcribe audio files using Whisper
- Support for various audio formats
- Speech-to-text conversion

📄 PDF PROCESSING:
- Extract text from PDF files
- Create PDF documents
- Handle multi-page documents

🔍 OCR (Image to Text):
- Extract text from images
- Support for screenshots
- Handwritten text recognition

📊 DATA FILES:
- Read/write CSV files
- Read/write Excel files
- Read/write JSON files
- Data format conversion

🔲 OTHER:
- Generate QR codes
- Convert Markdown to HTML
- File format detection

💡 BEST PRACTICES:
- For YouTube, extract video ID from any URL format
- For large transcripts, summarize key points
- For PDFs, mention page numbers when relevant
- For data files, preserve structure

🔧 AVAILABLE TOOLS:
- get_youtube_transcript: Get video captions
- search_youtube: Search for videos
- get_youtube_video_info: Get video details
- transcribe_audio: Convert audio to text
- extract_pdf_text: Extract PDF content
- create_pdf: Create new PDF
- ocr_image: Extract text from images
- read_csv / write_csv: CSV operations
- read_excel / write_excel: Excel operations
- read_json / write_json: JSON operations
- generate_qr_code: Create QR codes
- markdown_to_html: Convert markdown
"""

    def get_capabilities(self) -> List[str]:
        return [
            "Get YouTube video transcripts",
            "Search YouTube videos",
            "Get video information",
            "Transcribe audio files (Whisper)",
            "Extract text from PDFs",
            "Create PDF documents",
            "OCR - extract text from images",
            "Read and write CSV files",
            "Read and write Excel files",
            "Read and write JSON files",
            "Generate QR codes",
            "Convert Markdown to HTML"
        ]


def get_media_agent_tools() -> List[BaseTool]:
    """Get all tools for the Media Agent."""
    tools = []
    
    # YouTube tools
    try:
        from tools.youtube import (
            get_youtube_transcript,
            get_youtube_video_info,
            search_youtube
        )
        tools.extend([
            get_youtube_transcript,
            get_youtube_video_info,
            search_youtube,
        ])
    except ImportError:
        pass
    
    # Audio tools
    try:
        from tools.audio import transcribe_audio
        tools.append(transcribe_audio)
    except ImportError:
        pass
    
    # Document tools
    try:
        from tools.documents import (
            extract_pdf_text,
            create_pdf,
            ocr_image,
            read_csv,
            write_csv,
            read_excel,
            write_excel,
            read_json,
            write_json,
            markdown_to_html,
            generate_qr_code
        )
        tools.extend([
            extract_pdf_text,
            create_pdf,
            ocr_image,
            read_csv,
            write_csv,
            read_excel,
            write_excel,
            read_json,
            write_json,
            markdown_to_html,
            generate_qr_code,
        ])
    except ImportError:
        pass
    
    return tools


# Additional media tools
@tool
def summarize_youtube_video(video_url: str) -> str:
    """
    Get transcript and provide a summary-ready format for a YouTube video.
    
    Args:
        video_url: YouTube video URL or ID
        
    Returns:
        Video info and transcript ready for summarization
    """
    from tools.youtube import get_youtube_transcript, get_youtube_video_info
    
    # Get video info
    info = get_youtube_video_info.invoke({"video_url": video_url})
    
    # Get transcript
    transcript = get_youtube_transcript.invoke({
        "video_url": video_url,
        "language": "en"
    })
    
    return f"""
📺 YOUTUBE VIDEO SUMMARY REQUEST
══════════════════════════════════════════

{info}

📝 TRANSCRIPT:
{transcript}

══════════════════════════════════════════
💡 Use this content to generate a summary!
"""


@tool
def extract_document_text(file_path: str) -> str:
    """
    Smart document text extraction - automatically detects file type.
    
    Args:
        file_path: Path to the document (PDF, image, etc.)
        
    Returns:
        Extracted text content
    """
    import os
    
    if not os.path.exists(file_path):
        return f"❌ File not found: {file_path}"
    
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        from tools.documents import extract_pdf_text
        return extract_pdf_text.invoke({"file_path": file_path})
    
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
        from tools.documents import ocr_image
        return ocr_image.invoke({"image_path": file_path})
    
    elif ext == '.csv':
        from tools.documents import read_csv
        return read_csv.invoke({"file_path": file_path})
    
    elif ext in ['.xlsx', '.xls']:
        from tools.documents import read_excel
        return read_excel.invoke({"file_path": file_path})
    
    elif ext == '.json':
        from tools.documents import read_json
        return read_json.invoke({"file_path": file_path})
    
    elif ext in ['.txt', '.md', '.py', '.js', '.html', '.css']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"❌ Error reading file: {e}"
    
    else:
        return f"❌ Unsupported file type: {ext}"


@tool
def convert_data_format(
    input_path: str,
    output_format: str,
    output_path: str = ""
) -> str:
    """
    Convert between data formats (CSV, Excel, JSON).
    
    Args:
        input_path: Path to input file
        output_format: Target format (csv, excel, json)
        output_path: Optional output path (auto-generated if not provided)
        
    Returns:
        Confirmation of conversion
    """
    import os
    import json
    
    if not os.path.exists(input_path):
        return f"❌ File not found: {input_path}"
    
    ext = os.path.splitext(input_path)[1].lower()
    base = os.path.splitext(input_path)[0]
    
    # Generate output path if not provided
    format_extensions = {'csv': '.csv', 'excel': '.xlsx', 'json': '.json'}
    if not output_path:
        output_path = base + format_extensions.get(output_format, f'.{output_format}')
    
    try:
        import pandas as pd
        
        # Read input file
        if ext == '.csv':
            df = pd.read_csv(input_path)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(input_path)
        elif ext == '.json':
            df = pd.read_json(input_path)
        else:
            return f"❌ Unsupported input format: {ext}"
        
        # Write output file
        if output_format == 'csv':
            df.to_csv(output_path, index=False)
        elif output_format == 'excel':
            df.to_excel(output_path, index=False)
        elif output_format == 'json':
            df.to_json(output_path, orient='records', indent=2)
        else:
            return f"❌ Unsupported output format: {output_format}"
        
        return f"""
✅ CONVERSION COMPLETE
══════════════════════════════════════════

📥 Input: {input_path} ({ext})
📤 Output: {output_path} ({output_format})
📊 Records: {len(df)} rows

══════════════════════════════════════════
"""
    except ImportError:
        return "❌ pandas not installed. Install with: pip install pandas openpyxl"
    except Exception as e:
        return f"❌ Conversion failed: {e}"


if __name__ == "__main__":
    # Test the agent
    agent = MediaAgent()
    print("Media Agent initialized")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"\nCapabilities:\n" + "\n".join(f"  • {c}" for c in agent.get_capabilities()))
