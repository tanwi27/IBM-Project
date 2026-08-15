import json
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

def get_openai_client():
    try:
        from openai import OpenAI
        if settings.OPENAI_API_KEY:
            return OpenAI(api_key=settings.OPENAI_API_KEY)
    except ImportError:
        pass
    return None

def get_anthropic_client():
    try:
        from anthropic import Anthropic
        if settings.ANTHROPIC_API_KEY:
            return Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except ImportError:
        pass
    return None

def get_gemini_client():
    try:
        from google import genai
        if settings.GEMINI_API_KEY:
            # New Google GenAI SDK
            return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception:
        # Fallback to standard google-generativeai if installed, or openai-compatible
        pass
    return None

def get_gemini_openai_compatible_client():
    try:
        from openai import OpenAI
        if settings.GEMINI_API_KEY:
            return OpenAI(
                api_key=settings.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
    except ImportError:
        pass
    return None

def generate_llm_json(system_prompt: str, user_prompt: str, mock_fallback_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Unified entry point for calling the LLM and forcing a JSON response at temperature = 0.
    Falls back gracefully to mock structured data if API keys are missing.
    """
    provider = settings.PRIMARY_LLM_PROVIDER.lower()
    
    # 1. ANTHROPIC CLAUDE
    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        client = get_anthropic_client()
        if client:
            try:
                # Standard Anthropic JSON format using system prompt
                response = client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=4000,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt + "\n\nOutput only valid JSON."}
                    ]
                )
                content = response.content[0].text
                # Clean up any potential markdown formatting fences
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                return json.loads(content.strip())
            except Exception as e:
                logger.error(f"Anthropic API call failed: {e}")

    # 2. OPENAI GPT
    elif provider == "openai" and settings.OPENAI_API_KEY:
        client = get_openai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}")

    # 3. GOOGLE GEMINI
    elif provider == "gemini" and settings.GEMINI_API_KEY:
        # Use openai-compatible or google-genai client
        client = get_gemini_openai_compatible_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model=settings.GEMINI_MODEL,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"Gemini API call (OpenAI compatible) failed: {e}")

    # 4. GRACEFUL MOCK FALLBACK (If offline or keys are not provided)
    logger.warning(f"No API key provided for {provider} or API failed. Using deterministic fallback mock data.")
    if mock_fallback_data is not None:
        return mock_fallback_data
    return {"error": "No API response or fallback data available"}


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generates embeddings for a list of texts. 
    Supports Voyage AI, OpenAI, Gemini, or a local numpy random fallback to ensure operation offline.
    """
    provider = settings.EMBEDDING_PROVIDER.lower()
    
    # 1. VOYAGE AI
    if provider == "voyage" and settings.VOYAGE_API_KEY:
        try:
            import voyageai
            vo = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
            result = vo.embed(texts, model="voyage-2", input_type="document")
            return result.embeddings
        except Exception as e:
            logger.error(f"Voyage AI embedding failed: {e}")
            
    # 2. OPENAI
    elif provider == "openai" and settings.OPENAI_API_KEY:
        client = get_openai_client()
        if client:
            try:
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                logger.error(f"OpenAI embedding failed: {e}")

    # 3. GEMINI
    elif provider == "gemini" and settings.GEMINI_API_KEY:
        client = get_gemini_openai_compatible_client()
        if client:
            try:
                response = client.embeddings.create(
                    model="text-embedding-004",
                    input=texts
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                logger.error(f"Gemini embedding failed: {e}")

    # 4. LOCAL SENTENCE TRANSFORMERS (Optional, if installed)
    elif provider == "local":
        try:
            from sentence_transformers import SentenceTransformer
            # Using a very small, fast local model
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.warning(f"Local SentenceTransformers could not be loaded: {e}. Falling back to deterministic pseudo-embeddings.")

    # 5. DETERMINISTIC PSEUDO-EMBEDDINGS (Offline/Keyless fallback)
    # Generates a pseudo-embedding based on the hash of the text
    import hashlib
    import math
    
    embeddings = []
    dimension = 384  # MiniLM dimension
    for text in texts:
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()
        # Seed an algorithm to generate numbers between -1 and 1
        vec = []
        seed = int(h[:8], 16)
        for i in range(dimension):
            seed = (1103515245 * seed + 12345) & 0xffffffff
            val = (seed / 0xffffffff) * 2 - 1
            vec.append(val)
        # Normalize the vector
        magnitude = math.sqrt(sum(x*x for x in vec))
        normalized = [x / magnitude for x in vec]
        embeddings.append(normalized)
        
    return embeddings
