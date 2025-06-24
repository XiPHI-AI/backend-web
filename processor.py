import spacy
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

COMMON_SKILLS = [
    "python", "machine learning", "data analysis", "deep learning",
    "natural language processing", "computer vision", "cloud computing",
    "tensorflow", "pytorch", "sql", "aws", "gcp", "docker", "kubernetes"
]

COMMON_INTERESTS = [
    "ai", "open-source", "startups", "robotics", "sustainability",
    "blockchain", "ethics", "tech for good", "education", "research"
]

class TranscriptProcessor:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_lg")
        except OSError:
            logger.info("Downloading spaCy model...")
            spacy.cli.download("en_core_web_lg")
            self.nlp = spacy.load("en_core_web_lg")

    def match_keywords(self, doc, keyword_list):
        matched = set()
        for token in doc:
            for keyword in keyword_list:
                if self.nlp(keyword).similarity(token) > 0.7:
                    matched.add(keyword)
        return list(matched)

    def process_transcript(self, transcript: str) -> Dict[str, Any]:
        doc = self.nlp(transcript)

        result = {
            "skills": self.match_keywords(doc, COMMON_SKILLS),
            "expertise": [],
            "interests": self.match_keywords(doc, COMMON_INTERESTS),
            "education": [],
            "job_history": [],
            "company": None,
            "location": None
        }

        for sent in doc.sents:
            text = sent.text.lower()
            # Extract expertise if described
            if "expertise in" in text:
                result["expertise"].append(sent.text.split("expertise in")[-1].strip())
            elif "experienced in" in text:
                result["expertise"].append(sent.text.split("experienced in")[-1].strip())
            
            # Extract job role and company
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

        # Deduplicate everything
        result["skills"] = sorted(set(result["skills"]))
        result["expertise"] = sorted(set(e.strip() for e in result["expertise"] if e.strip()))
        result["interests"] = sorted(set(result["interests"]))

        return result
if __name__ == "__main__":
    processor = TranscriptProcessor()

    sample_transcript = """
    I'm a software engineer with expertise in Python and machine learning.
    I'm particularly interested in natural language processing and computer vision.
    I graduated from Stanford University with a degree in Computer Science.
    I'm currently working at Google where I'm proficient in cloud technologies.
    I'm passionate about AI and enjoy working on open-source projects.
    """

    result = processor.process_transcript(sample_transcript)
    print(json.dumps(result, indent=2))
