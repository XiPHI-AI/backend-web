import spacy
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    def __init__(self, google_api_key: Optional[str] = None):
        # Initialize spaCy as a fallback
        try:
            self.nlp = spacy.load("en_core_web_lg")
        except OSError:
            logger.info("Downloading spaCy model...")
            spacy.cli.download("en_core_web_lg")
            self.nlp = spacy.load("en_core_web_lg")

        # Initialize LangChain with Gemini API
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("Google API key not provided. Set GOOGLE_API_KEY environment variable or pass it explicitly.")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=self.google_api_key,
            temperature=0.0
        )

        # Prompt updated to include 'name'
        self.prompt_template = PromptTemplate(
            input_variables=["transcript"],
            template="""
You are an expert in extracting structured information from text. Given the following transcript, extract the following fields in JSON format:
- name: Full name of the individual
- skills: List of technical skills (e.g., python, sql, data visualization)
- expertise: List of areas of expertise (e.g., cloud platforms, data pipelines)(Dont use short forms)
- interests: List of interests (e.g., ai, open-source)
- education: List of education entries with institution, degree, and year (if available)
- job_history: List of job history entries with role, company, start_year, and end_year (if available)
- company: Current company name
- location: Geographical location (e.g., city, country)

Transcript:
{transcript}

Output the result as a JSON object. If a field cannot be determined, return it as null or an empty list. Ensure the output is valid JSON.
            """
        )

        self.chain = LLMChain(llm=self.llm, prompt=self.prompt_template)

    def process_with_gemini(self, transcript: str) -> Dict[str, Any]:
        try:
            response = self.chain.run(transcript=transcript)
            result = json.loads(response.strip("```json\n").strip("```"))
            return result
        except Exception as e:
            logger.error(f"Gemini API via LangChain failed: {e}. Falling back to spaCy processing.")
            return self.process_with_spacy(transcript)

    def process_with_spacy(self, transcript: str) -> Dict[str, Any]:
        doc = self.nlp(transcript)

        result = {
            "name": None,
            "skills": [],
            "expertise": [],
            "interests": [],
            "education": [],
            "job_history": [],
            "company": None,
            "location": None
        }

        for sent in doc.sents:
            text = sent.text.lower()
            if "expertise in" in text:
                result["expertise"].append(sent.text.split("expertise in")[-1].strip())
            elif "experienced in" in text:
                result["expertise"].append(sent.text.split("experienced in")[-1].strip())
            
            if "working at" in text or "work at" in text:
                result["company"] = sent[-1].text.title()
                result["job_history"].append({
                    "role": "Unknown",
                    "company": result["company"],
                    "start_year": None,
                    "end_year": None
                })

        for ent in doc.ents:
            if ent.label_ == "ORG":
                if any(word in ent.text.lower() for word in ["university", "college", "institute", "school"]):
                    result["education"].append({
                        "institution": ent.text,
                        "degree": None,
                        "year": None
                    })
                elif not result["company"]:
                    result["company"] = ent.text
            elif ent.label_ == "GPE":
                result["location"] = ent.text
            elif ent.label_ == "PERSON" and not result["name"]:
                result["name"] = ent.text

        result["expertise"] = sorted(set(e.strip() for e in result["expertise"] if e.strip()))

        return result

    def process_transcript(self, transcript: str) -> Dict[str, Any]:
        return self.process_with_gemini(transcript)

if __name__ == "__main__":
    processor = TranscriptProcessor(google_api_key="YOUR_GOOGLE_API_KEY")

    print("Enter your transcript (press Enter twice to finish):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    transcript = "\n".join(lines)

    if not transcript.strip():
        print("No transcript provided. Exiting.")
    else:
        result = processor.process_transcript(transcript)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcript_output_{timestamp}.json"
        with open(filename, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Transcript processed and saved to {filename}")
