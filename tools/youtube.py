"""
YouTube Tools - Get video transcripts and information
Uses youtube-transcript-api (no API key needed!)
"""

import os
import re
import logging
from langchain_core.tools import tool

logger = logging.getLogger("Orion")


def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from YouTube URL or return as-is if already an ID."""
    # If it's already just an ID (11 characters)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # Try to extract from various URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    return url_or_id  # Return as-is, let the API handle the error


@tool
def get_youtube_transcript(video_url: str, language: str = "en") -> str:
    """
    Get the transcript/captions of a YouTube video.
    
    Args:
        video_url: YouTube video URL or video ID (e.g., 'dQw4w9WgXcQ' or 'https://youtube.com/watch?v=dQw4w9WgXcQ')
        language: Language code for transcript (default: 'en'). Try 'hi' for Hindi.
    
    Returns:
        The full transcript text of the video
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
        
        video_id = extract_video_id(video_url)
        logger.info(f"Fetching transcript for video: {video_id}")
        
        try:
            # Try to get transcript in requested language
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try manual transcript first, then auto-generated
            try:
                transcript = transcript_list.find_manually_created_transcript([language, 'en', 'hi'])
            except:
                transcript = transcript_list.find_generated_transcript([language, 'en', 'hi'])
            
            transcript_data = transcript.fetch()
            
        except (TranscriptsDisabled, NoTranscriptFound):
            # Fallback: try to get any available transcript
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine all text segments
        full_text = " ".join([entry['text'] for entry in transcript_data])
        
        # Clean up the text
        full_text = re.sub(r'\[.*?\]', '', full_text)  # Remove [Music], [Applause] etc
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        # Truncate if too long (for LLM context)
        if len(full_text) > 15000:
            full_text = full_text[:15000] + "... [transcript truncated]"
        
        return f"📺 Transcript for video {video_id}:\n\n{full_text}"
        
    except ImportError:
        return "❌ youtube-transcript-api not installed. Run: pip install youtube-transcript-api"
    except Exception as e:
        logger.error(f"YouTube transcript error: {e}")
        return f"❌ Could not get transcript: {str(e)}"


@tool
def get_youtube_video_info(video_url: str) -> str:
    """
    Get basic information about a YouTube video (title, channel, duration).
    Uses yt-dlp for metadata extraction.
    
    Args:
        video_url: YouTube video URL or video ID
    
    Returns:
        Video title, channel, duration, view count, and description
    """
    try:
        import yt_dlp
        
        video_id = extract_video_id(video_url)
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        title = info.get('title', 'Unknown')
        channel = info.get('channel', info.get('uploader', 'Unknown'))
        duration = info.get('duration', 0)
        views = info.get('view_count', 0)
        description = info.get('description', '')[:500]
        upload_date = info.get('upload_date', '')
        
        # Format duration
        if duration:
            mins, secs = divmod(duration, 60)
            hours, mins = divmod(mins, 60)
            if hours:
                duration_str = f"{hours}h {mins}m {secs}s"
            else:
                duration_str = f"{mins}m {secs}s"
        else:
            duration_str = "Unknown"
        
        # Format upload date
        if upload_date:
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        
        # Format view count
        if views:
            if views >= 1_000_000:
                views_str = f"{views/1_000_000:.1f}M"
            elif views >= 1_000:
                views_str = f"{views/1_000:.1f}K"
            else:
                views_str = str(views)
        else:
            views_str = "Unknown"
        
        result = f"""🎬 **{title}**

📺 Channel: {channel}
⏱️ Duration: {duration_str}
👁️ Views: {views_str}
📅 Uploaded: {upload_date}

📝 Description:
{description}{'...' if len(info.get('description', '')) > 500 else ''}
"""
        return result
        
    except ImportError:
        return "❌ yt-dlp not installed. Run: pip install yt-dlp"
    except Exception as e:
        logger.error(f"YouTube info error: {e}")
        return f"❌ Could not get video info: {str(e)}"


@tool  
def search_youtube(query: str, max_results: int = 5) -> str:
    """
    Search YouTube for videos matching a query.
    
    Args:
        query: Search query (e.g., "python tutorial", "cooking recipes")
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        List of video titles with URLs
    """
    try:
        from youtubesearchpython import VideosSearch
        
        search = VideosSearch(query, limit=max_results)
        results = search.result()
        
        if not results.get('result'):
            return f"No results found for: {query}"
        
        output = [f"🔍 YouTube search results for: **{query}**\n"]
        
        for i, video in enumerate(results['result'], 1):
            title = video.get('title', 'Unknown')
            channel = video.get('channel', {}).get('name', 'Unknown')
            duration = video.get('duration', 'Unknown')
            views = video.get('viewCount', {}).get('short', 'Unknown')
            url = video.get('link', '')
            
            output.append(f"{i}. **{title}**")
            output.append(f"   📺 {channel} | ⏱️ {duration} | 👁️ {views}")
            output.append(f"   🔗 {url}\n")
        
        return "\n".join(output)
        
    except ImportError:
        return "❌ youtube-search-python not installed. Run: pip install youtube-search-python"
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return f"❌ Search failed: {str(e)}"


def get_youtube_tools():
    """Return all YouTube-related tools."""
    return [
        get_youtube_transcript,
        get_youtube_video_info,
        search_youtube,
    ]
