import streamlit as st
from groq import Groq
import os
import json

# Groq API Client initialized with Streamlit secrets
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    # Fallback to environment variable if secrets are not available
    client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

@st.cache_data(show_spinner=False)
def get_chart_insight(data_context, persona="Data Scientist"):
    """
    Generate AI insights for a given chart data context using Groq.
    
    Personas:
    - Storyteller: Narrative journey.
    - Strategist: Growth/Threats.
    - Data Scientist: Statistical anomalies/Z-scores.
    """
    
    prompt_templates = {
        "Storyteller": "You are a Storyteller. Describe the narrative journey of this data. What is the 'human' story behind these numbers? Keep it engaging and descriptive.",
        "Strategist": "You are a Strategist. Analyze these numbers for growth opportunities and potential threats. What should the business do next based on this trend?",
        "Data Scientist": "You are a Data Scientist. Focus on statistical anomalies, significance, and data-driven insights. Mention any Z-scores or significant variances you observe."
    }
    
    persona_prompt = prompt_templates.get(persona, prompt_templates["Data Scientist"])
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"{persona_prompt} Always reference the specific numbers provided. Keep the response concise (max 150 words)."},
                {"role": "user", "content": f"Data Context: {json.dumps(data_context)}"}
            ],
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        if "429" in str(e):
            return "⚠️ AI rate limit reached (Groq Free Tier). Please try again in a minute."
        return f"❌ Error generating insight: {str(e)}"

def analyze_chart_ui(chart_id, data_df, chart_name):
    """
    Reusable UI component for chart analysis.
    """
    with st.expander(f"🤖 Analyze {chart_name}"):
        col1, col2 = st.columns([3, 1])
        with col2:
            persona = st.selectbox("Persona", ["Data Scientist", "Strategist", "Storyteller"], key=f"persona_{chart_id}")
            analyze_btn = st.button("Generate Insight", key=f"btn_{chart_id}")
            
        with col1:
            if analyze_btn:
                # Prepare minimal data context
                data_context = {
                    "chart": chart_name,
                    "metrics": data_df.to_dict(orient='records')
                }
                
                with st.spinner("AI is thinking..."):
                    insight = get_chart_insight(data_context, persona)
                    st.markdown(f"""
                        <div style="background-color: #1e1e1e; padding: 15px; border-left: 5px solid #e31837; border-radius: 5px; color: white;">
                            {insight}
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Select a persona and click 'Generate Insight' to see AI analysis.")
