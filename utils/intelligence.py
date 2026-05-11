import json
import os
import re
import time
from groq import Groq, RateLimitError, InternalServerError, APIStatusError, APIConnectionError
import streamlit as st

class IntelligenceVault:
    def __init__(self, vault_path="data/insights_vault.json"):
        self.vault_path = vault_path
        self.vault_data = self._load_vault()

    def _load_vault(self):
        if os.path.exists(self.vault_path):
            try:
                with open(self.vault_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_vault(self):
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        temp_path = f"{self.vault_path}.tmp"
        try:
            with open(temp_path, 'w') as f:
                json.dump(self.vault_data, f, indent=4)
            os.replace(temp_path, self.vault_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def get_insights(self, model, period):
        key = f"{model}_{period}"
        return self.vault_data.get(key)

    def save_insights(self, model, period, insights):
        key = f"{model}_{period}"
        self.vault_data[key] = insights
        self._save_vault()

def get_sentiment_flag(text):
    """
    Returns a sentiment flag based on keywords.
    """
    text = text.lower()
    pos_keywords = ["growth", "increase", "opportunity", "positive", "strong", "leadership", "improvement", "success"]
    neg_keywords = ["threat", "decline", "warning", "negative", "weak", "saturated", "risk", "decrease", "friction"]
    
    pos_score = sum(1 for word in pos_keywords if word in text)
    neg_score = sum(1 for word in neg_keywords if word in text)
    
    if pos_score > neg_score:
        return "Positive"
    elif neg_score > pos_score:
        return "Warning"
    return "Neutral"

def parse_briefing_response(response_text):
    """
    Parses the Groq response which could be in JSON or tagged blocks.
    """
    insights = {
        "storyteller": "",
        "strategist": "",
        "scientist": ""
    }

    # 1. Try to find JSON in markdown blocks
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            insights.update(data)
            return insights
        except json.JSONDecodeError:
            pass

    # 2. Try to find tags like <storyteller>...</storyteller>
    for persona in ["storyteller", "strategist", "scientist"]:
        tag_match = re.search(f'<{persona}>(.*?)</{persona}>', response_text, re.DOTALL)
        if tag_match:
            insights[persona] = tag_match.group(1).strip()

    # 3. If nothing found, use storyteller as fallback for the whole text
    if not any(insights.values()):
        insights["storyteller"] = response_text.strip()

    return insights

def generate_showroom_briefing(model_data, model_name, period="Monthly"):
    """
    Generates a bulk briefing for the entire model performance.
    """
    # Groq API Client
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return {
            "storyteller": "⚠️ Configuration Error: Groq API Key not found. Please check your environment variables or Streamlit secrets.",
            "strategist": "⚠️ System offline: Intelligence engine requires an API key to provide strategic recommendations.",
            "scientist": "⚠️ Data analysis unavailable: Connect your AI engine to proceed with statistical modeling."
        }

    client = Groq(api_key=api_key)
    
    prompt = f"""
    You are a triple-persona market intelligence engine for Royal Enfield.
    Analyze the following market data for the model: {model_name} ({period} period).
    
    Data Context:
    {json.dumps(model_data, indent=2)}
    
    Provide your analysis from three perspectives:
    1. <storyteller>: The human narrative and buyer journey.
    2. <strategist>: Growth opportunities, competitive threats, and business recommendations.
    3. <scientist>: Statistical anomalies, significance levels, and data-driven facts.
    
    Output MUST be in valid JSON format inside a ```json code block with keys: "storyteller", "strategist", "scientist".
    Keep each persona's response concise (under 100 words each).
    Reference specific numbers from the data.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a professional automotive market analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            return parse_briefing_response(response.choices[0].message.content)
        
        except RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {
                "storyteller": "⏳ The intelligence engine is currently overloaded.",
                "strategist": "⏳ Strategic analysis is delayed due to high traffic.",
                "scientist": "⏳ Statistical processing has timed out. Please try again in a few minutes."
            }
        
        except (InternalServerError, APIConnectionError):
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {
                "storyteller": "🔌 Connection lost: Unable to reach the storyteller module.",
                "strategist": "🔌 Network error: Strategist insights are temporarily unavailable.",
                "scientist": "🔌 System failure: Scientific data engine is unresponsive."
            }
            
        except APIStatusError as e:
            if e.status_code >= 500 and attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {
                "storyteller": "🚫 Service interrupted: The intelligence engine encountered an API error.",
                "strategist": "🚫 Strategy module offline: Error communicating with the analysis server.",
                "scientist": "🚫 Data link broken: Scientific verification could not be completed."
            }
            
        except Exception:
            return {
                "storyteller": "❌ Unexpected error: The storyteller module encountered a processing glitch.",
                "strategist": "❌ Analysis failed: The strategist module is unable to process this data.",
                "scientist": "❌ Computation error: The scientist module failed to generate data insights."
            }
    
    return {
        "storyteller": "⚠️ Maximum retries exceeded. Narrative generation failed.",
        "strategist": "⚠️ Maximum retries exceeded. Strategy analysis failed.",
        "scientist": "⚠️ Maximum retries exceeded. Data processing failed."
    }
