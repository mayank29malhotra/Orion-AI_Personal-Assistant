"""
Document Tools for Orion
PDF, OCR, CSV, Excel, JSON, and Markdown processing.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from langchain_core.tools.simple import Tool

logger = logging.getLogger("Orion")

# Data directory
DATA_DIR = Path("sandbox/data")


def _ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


# ============ PDF TOOLS ============

def extract_pdf_text(file_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        file_path: Path to the PDF file
    """
    try:
        import pypdf
        
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"
        
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            text_parts = []
            
            for i, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i} ---\n{page_text}")
        
        if not text_parts:
            return "📄 PDF appears to be empty or image-based. Try OCR instead."
        
        result = "\n\n".join(text_parts)
        logger.info(f"Extracted text from {len(reader.pages)} pages of {file_path}")
        
        # Truncate if too long
        if len(result) > 10000:
            return result[:10000] + "\n\n... (truncated, file is very long)"
        
        return result
    
    except ImportError:
        return "❌ pypdf not installed. Install with: pip install pypdf"
    except Exception as e:
        error_msg = f"Failed to extract PDF text: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def create_pdf(content: str, output_path: str, title: str = "Document") -> str:
    """
    Create a PDF from text content.
    
    Args:
        content: Text content for the PDF
        output_path: Output file path
        title: Document title
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(inch, height - inch, title)
        
        # Content
        c.setFont("Helvetica", 11)
        y = height - 1.5 * inch
        
        for line in content.split('\n'):
            if y < inch:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - inch
            
            # Wrap long lines
            while len(line) > 80:
                c.drawString(inch, y, line[:80])
                line = line[80:]
                y -= 14
                if y < inch:
                    c.showPage()
                    c.setFont("Helvetica", 11)
                    y = height - inch
            
            c.drawString(inch, y, line)
            y -= 14
        
        c.save()
        logger.info(f"PDF created: {output_path}")
        return f"✅ PDF created: {output_path}"
    
    except ImportError:
        return "❌ reportlab not installed. Install with: pip install reportlab"
    except Exception as e:
        error_msg = f"Failed to create PDF: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ OCR TOOLS ============

def ocr_image(image_path: str) -> str:
    """
    Extract text from an image using OCR.
    
    Args:
        image_path: Path to the image file
    """
    try:
        import pytesseract
        from PIL import Image
        
        if not os.path.exists(image_path):
            return f"❌ Image not found: {image_path}"
        
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        
        if not text.strip():
            return "📷 No text detected in image"
        
        logger.info(f"OCR completed for: {image_path}")
        return f"📷 OCR Result:\n{text}"
    
    except ImportError:
        return "❌ pytesseract/PIL not installed. Install with: pip install pytesseract pillow"
    except Exception as e:
        error_msg = f"OCR failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ CSV TOOLS ============

def read_csv(file_path: str, limit: int = 100) -> str:
    """
    Read a CSV file and return its contents.
    
    Args:
        file_path: Path to the CSV file
        limit: Maximum number of rows to return (default 100)
    """
    try:
        import pandas as pd
        
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"
        
        df = pd.read_csv(file_path, nrows=limit)
        
        result = f"📊 CSV: {file_path}\n"
        result += f"📏 Shape: {df.shape[0]} rows × {df.shape[1]} columns\n"
        result += f"📋 Columns: {', '.join(df.columns)}\n\n"
        result += df.to_string(max_rows=20)
        
        if len(df) > 20:
            result += f"\n\n... (showing first 20 of {len(df)} rows)"
        
        logger.info(f"CSV read: {file_path}")
        return result
    
    except ImportError:
        return "❌ pandas not installed. Install with: pip install pandas"
    except Exception as e:
        error_msg = f"Failed to read CSV: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def write_csv(data: str, output_path: str, headers: str = None) -> str:
    """
    Write data to a CSV file.
    
    Args:
        data: Data as JSON array of arrays or objects
        output_path: Output file path
        headers: Comma-separated headers (optional, inferred from data if objects)
    """
    try:
        import pandas as pd
        
        # Parse data
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return "❌ Data must be valid JSON. Example: [[1,2,3],[4,5,6]] or [{\"a\":1},{\"a\":2}]"
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(parsed[0], dict):
            df = pd.DataFrame(parsed)
        else:
            if headers:
                cols = [h.strip() for h in headers.split(',')]
            else:
                cols = None
            df = pd.DataFrame(parsed, columns=cols)
        
        df.to_csv(output_path, index=False)
        
        logger.info(f"CSV written: {output_path}")
        return f"✅ CSV written: {output_path} ({len(df)} rows)"
    
    except ImportError:
        return "❌ pandas not installed. Install with: pip install pandas"
    except Exception as e:
        error_msg = f"Failed to write CSV: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ EXCEL TOOLS ============

def read_excel(file_path: str, sheet_name: str = None, limit: int = 100) -> str:
    """
    Read an Excel file.
    
    Args:
        file_path: Path to the Excel file
        sheet_name: Sheet name to read (optional, reads first sheet by default)
        limit: Maximum rows to return
    """
    try:
        import pandas as pd
        
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"
        
        # Get sheet names
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        
        target_sheet = sheet_name if sheet_name else sheets[0]
        df = pd.read_excel(file_path, sheet_name=target_sheet, nrows=limit)
        
        result = f"📊 Excel: {file_path}\n"
        result += f"📑 Sheets: {', '.join(sheets)}\n"
        result += f"📖 Reading: {target_sheet}\n"
        result += f"📏 Shape: {df.shape[0]} rows × {df.shape[1]} columns\n\n"
        result += df.to_string(max_rows=20)
        
        logger.info(f"Excel read: {file_path}")
        return result
    
    except ImportError:
        return "❌ pandas/openpyxl not installed. Install with: pip install pandas openpyxl"
    except Exception as e:
        error_msg = f"Failed to read Excel: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def write_excel(data: str, output_path: str, sheet_name: str = "Sheet1") -> str:
    """
    Write data to an Excel file.
    
    Args:
        data: Data as JSON array
        output_path: Output file path
        sheet_name: Sheet name (default: Sheet1)
    """
    try:
        import pandas as pd
        
        parsed = json.loads(data)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(parsed[0], dict):
            df = pd.DataFrame(parsed)
        else:
            df = pd.DataFrame(parsed)
        
        df.to_excel(output_path, sheet_name=sheet_name, index=False)
        
        logger.info(f"Excel written: {output_path}")
        return f"✅ Excel written: {output_path} ({len(df)} rows)"
    
    except ImportError:
        return "❌ pandas/openpyxl not installed. Install with: pip install pandas openpyxl"
    except Exception as e:
        error_msg = f"Failed to write Excel: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ JSON TOOLS ============

def read_json(file_path: str) -> str:
    """
    Read a JSON file.
    
    Args:
        file_path: Path to the JSON file
    """
    try:
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = json.dumps(data, indent=2)
        
        if len(result) > 5000:
            result = result[:5000] + "\n\n... (truncated)"
        
        logger.info(f"JSON read: {file_path}")
        return f"📄 JSON: {file_path}\n\n{result}"
    
    except Exception as e:
        error_msg = f"Failed to read JSON: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def write_json(data: str, output_path: str) -> str:
    """
    Write data to a JSON file.
    
    Args:
        data: JSON string to write
        output_path: Output file path
    """
    try:
        # Validate JSON
        parsed = json.loads(data)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, indent=2)
        
        logger.info(f"JSON written: {output_path}")
        return f"✅ JSON written: {output_path}"
    
    except json.JSONDecodeError as e:
        return f"❌ Invalid JSON: {str(e)}"
    except Exception as e:
        error_msg = f"Failed to write JSON: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ MARKDOWN TOOLS ============

def markdown_to_html(markdown_text: str, output_path: str = None) -> str:
    """
    Convert markdown to HTML.
    
    Args:
        markdown_text: Markdown content to convert
        output_path: Optional output file path
    """
    try:
        import markdown
        
        html = markdown.markdown(
            markdown_text,
            extensions=['tables', 'fenced_code', 'toc']
        )
        
        # Wrap in basic HTML template
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 800px; margin: 40px auto; padding: 20px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; overflow-x: auto; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    </style>
</head>
<body>
{html}
</body>
</html>"""
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_html)
            logger.info(f"HTML written: {output_path}")
            return f"✅ HTML created: {output_path}"
        
        return full_html
    
    except ImportError:
        return "❌ markdown not installed. Install with: pip install markdown"
    except Exception as e:
        error_msg = f"Markdown conversion failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ QR CODE ============

def generate_qr_code(data: str, output_path: str = None) -> str:
    """
    Generate a QR code image.
    
    Args:
        data: Data to encode in QR code (URL, text, etc.)
        output_path: Output image path (optional, defaults to sandbox/data/qrcode.png)
    """
    try:
        import qrcode
        
        if not output_path:
            output_path = str(_ensure_data_dir() / "qrcode.png")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
        
        logger.info(f"QR code generated: {output_path}")
        return f"✅ QR code generated: {output_path}"
    
    except ImportError:
        return "❌ qrcode not installed. Install with: pip install qrcode[pil]"
    except Exception as e:
        error_msg = f"QR code generation failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ TOOL EXPORTS ============

def get_pdf_tools():
    """Get PDF-related tools."""
    return [
        Tool(
            name="extract_pdf_text",
            func=extract_pdf_text,
            description="Extract text from a PDF file. Args: file_path"
        ),
        Tool(
            name="create_pdf",
            func=create_pdf,
            description="Create a PDF from text content. Args: content, output_path, title (optional)"
        ),
    ]


def get_ocr_tools():
    """Get OCR tools."""
    return [
        Tool(
            name="ocr_image",
            func=ocr_image,
            description="Extract text from an image using OCR. Args: image_path"
        ),
    ]


def get_csv_tools():
    """Get CSV-related tools."""
    return [
        Tool(
            name="read_csv",
            func=read_csv,
            description="Read a CSV file. Args: file_path, limit (optional, default 100)"
        ),
        Tool(
            name="write_csv",
            func=write_csv,
            description="Write data to CSV. Args: data (JSON array), output_path, headers (optional)"
        ),
    ]


def get_excel_tools():
    """Get Excel-related tools."""
    return [
        Tool(
            name="read_excel",
            func=read_excel,
            description="Read an Excel file. Args: file_path, sheet_name (optional), limit (optional)"
        ),
        Tool(
            name="write_excel",
            func=write_excel,
            description="Write data to Excel. Args: data (JSON), output_path, sheet_name (optional)"
        ),
    ]


def get_json_tools():
    """Get JSON-related tools."""
    return [
        Tool(
            name="read_json",
            func=read_json,
            description="Read a JSON file. Args: file_path"
        ),
        Tool(
            name="write_json",
            func=write_json,
            description="Write JSON to file. Args: data (JSON string), output_path"
        ),
    ]


def get_markdown_tools():
    """Get Markdown tools."""
    return [
        Tool(
            name="markdown_to_html",
            func=markdown_to_html,
            description="Convert markdown to HTML. Args: markdown_text, output_path (optional)"
        ),
    ]


def get_qr_tools():
    """Get QR code tools."""
    return [
        Tool(
            name="generate_qr_code",
            func=generate_qr_code,
            description="Generate a QR code image. Args: data (text/URL), output_path (optional)"
        ),
    ]


def get_document_tools():
    """Get all document-related tools."""
    return (
        get_pdf_tools() +
        get_ocr_tools() +
        get_csv_tools() +
        get_excel_tools() +
        get_json_tools() +
        get_markdown_tools() +
        get_qr_tools()
    )
