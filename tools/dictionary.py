"""
Dictionary Tools - Word definitions, synonyms, pronunciation
Uses Free Dictionary API (no API key needed!)
"""

import os
import logging
import requests
from langchain_core.tools import tool

logger = logging.getLogger("Orion")

FREE_DICTIONARY_API = "https://api.dictionaryapi.dev/api/v2/entries/en"


@tool
def define_word(word: str) -> str:
    """
    Get the definition of an English word including pronunciation, meanings, and examples.
    
    Args:
        word: The word to define (e.g., "serendipity", "ephemeral")
    
    Returns:
        Word definition with pronunciation, part of speech, meanings, and example sentences
    """
    try:
        word = word.strip().lower()
        response = requests.get(f"{FREE_DICTIONARY_API}/{word}", timeout=10)
        
        if response.status_code == 404:
            return f"❌ Word '{word}' not found in dictionary. Check spelling."
        
        response.raise_for_status()
        data = response.json()
        
        if not data or not isinstance(data, list):
            return f"❌ No definition found for '{word}'"
        
        entry = data[0]
        result = [f"📖 **{entry.get('word', word).title()}**"]
        
        # Phonetics/Pronunciation
        phonetics = entry.get('phonetics', [])
        for p in phonetics:
            if p.get('text'):
                result.append(f"🔊 Pronunciation: {p['text']}")
                break
        
        # Meanings
        meanings = entry.get('meanings', [])
        for meaning in meanings:
            pos = meaning.get('partOfSpeech', 'unknown')
            result.append(f"\n**{pos.title()}:**")
            
            definitions = meaning.get('definitions', [])[:3]  # Max 3 definitions per POS
            for i, defn in enumerate(definitions, 1):
                definition = defn.get('definition', '')
                example = defn.get('example', '')
                
                result.append(f"  {i}. {definition}")
                if example:
                    result.append(f"     💬 *\"{example}\"*")
            
            # Synonyms
            synonyms = meaning.get('synonyms', [])[:5]
            if synonyms:
                result.append(f"  ✅ Synonyms: {', '.join(synonyms)}")
            
            # Antonyms
            antonyms = meaning.get('antonyms', [])[:5]
            if antonyms:
                result.append(f"  ❌ Antonyms: {', '.join(antonyms)}")
        
        return "\n".join(result)
        
    except requests.Timeout:
        return "❌ Dictionary API timeout. Try again."
    except requests.RequestException as e:
        logger.error(f"Dictionary API error: {e}")
        return f"❌ Could not fetch definition: {str(e)}"
    except Exception as e:
        logger.error(f"Dictionary error: {e}")
        return f"❌ Error: {str(e)}"


@tool
def get_synonyms(word: str) -> str:
    """
    Get synonyms (similar words) for an English word.
    
    Args:
        word: The word to find synonyms for
    
    Returns:
        List of synonyms grouped by part of speech
    """
    try:
        word = word.strip().lower()
        response = requests.get(f"{FREE_DICTIONARY_API}/{word}", timeout=10)
        
        if response.status_code == 404:
            return f"❌ Word '{word}' not found. Check spelling."
        
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return f"❌ No synonyms found for '{word}'"
        
        entry = data[0]
        result = [f"✅ **Synonyms for '{word}':**\n"]
        
        found_any = False
        for meaning in entry.get('meanings', []):
            pos = meaning.get('partOfSpeech', '')
            synonyms = meaning.get('synonyms', [])
            
            # Also collect synonyms from definitions
            for defn in meaning.get('definitions', []):
                synonyms.extend(defn.get('synonyms', []))
            
            synonyms = list(set(synonyms))[:10]  # Unique, max 10
            
            if synonyms:
                found_any = True
                result.append(f"**{pos.title()}:** {', '.join(synonyms)}")
        
        if not found_any:
            return f"No synonyms found for '{word}'"
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Synonyms error: {e}")
        return f"❌ Error: {str(e)}"


@tool
def get_antonyms(word: str) -> str:
    """
    Get antonyms (opposite words) for an English word.
    
    Args:
        word: The word to find antonyms for
    
    Returns:
        List of antonyms grouped by part of speech
    """
    try:
        word = word.strip().lower()
        response = requests.get(f"{FREE_DICTIONARY_API}/{word}", timeout=10)
        
        if response.status_code == 404:
            return f"❌ Word '{word}' not found. Check spelling."
        
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return f"❌ No antonyms found for '{word}'"
        
        entry = data[0]
        result = [f"❌ **Antonyms for '{word}':**\n"]
        
        found_any = False
        for meaning in entry.get('meanings', []):
            pos = meaning.get('partOfSpeech', '')
            antonyms = meaning.get('antonyms', [])
            
            # Also collect antonyms from definitions
            for defn in meaning.get('definitions', []):
                antonyms.extend(defn.get('antonyms', []))
            
            antonyms = list(set(antonyms))[:10]  # Unique, max 10
            
            if antonyms:
                found_any = True
                result.append(f"**{pos.title()}:** {', '.join(antonyms)}")
        
        if not found_any:
            return f"No antonyms found for '{word}'"
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Antonyms error: {e}")
        return f"❌ Error: {str(e)}"


@tool
def translate_word(word: str, to_language: str = "hi") -> str:
    """
    Translate a word to another language using MyMemory Translation API.
    
    Args:
        word: The word or phrase to translate
        to_language: Target language code (e.g., 'hi' for Hindi, 'es' for Spanish, 'fr' for French)
    
    Returns:
        Translated text
    
    Common language codes:
        hi=Hindi, es=Spanish, fr=French, de=German, zh=Chinese, 
        ja=Japanese, ko=Korean, ar=Arabic, ru=Russian, pt=Portuguese
    """
    try:
        word = word.strip()
        
        # MyMemory Translation API (free, no key needed)
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": word,
            "langpair": f"en|{to_language}"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('responseStatus') == 200:
            translated = data.get('responseData', {}).get('translatedText', '')
            
            # Language names
            lang_names = {
                'hi': 'Hindi', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
                'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean', 'ar': 'Arabic',
                'ru': 'Russian', 'pt': 'Portuguese', 'it': 'Italian', 'nl': 'Dutch',
                'ta': 'Tamil', 'te': 'Telugu', 'bn': 'Bengali', 'mr': 'Marathi',
            }
            lang_name = lang_names.get(to_language, to_language.upper())
            
            return f"🌐 **Translation to {lang_name}:**\n\n{word} → **{translated}**"
        else:
            return f"❌ Translation failed: {data.get('responseDetails', 'Unknown error')}"
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return f"❌ Translation error: {str(e)}"


def get_dictionary_tools():
    """Return all dictionary-related tools."""
    return [
        define_word,
        get_synonyms,
        get_antonyms,
        translate_word,
    ]
