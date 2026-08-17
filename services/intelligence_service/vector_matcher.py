import os
import json
import gzip
import time
import numpy as np
from typing import List, Dict, Any, Optional
from fastembed import TextEmbedding

class VectorMatcher:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        """
        Initializes the FastEmbed ONNX runtime engine.
        BAAI/bge-small-en-v1.5 produces 384-dimensional dense vectors.
        """
        print(f"[*] Initializing local FastEmbed ONNX model: {model_name}...")
        self.model_name = model_name
        self.model = TextEmbedding(model_name=model_name)
        print("[✓] FastEmbed engine ready (running on local ONNX Runtime).")

    def build_profile_semantic_doc(self, profile: Dict[str, Any]) -> str:
        """
        Flattens the structured JSON profile into an information-dense semantic document.
        """
        sections = []

        # 1. Summary
        if profile.get("summary"):
            sections.append(f"Candidate Summary: {profile['summary']}")

        # 2. Technical Skills
        skills = profile.get("skills", [])
        if skills:
            skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
            sections.append(f"Core Skills & Technologies: {skills_str}")

        # 3. Key Projects
        for proj in profile.get("projects", []):
            title = proj.get("title", "")
            role = proj.get("role", "")
            tech = ", ".join(proj.get("technologies", []))
            highlights = " ".join(proj.get("highlights", []))
            sections.append(
                f"Project: {title} | Role: {role} | Technologies: {tech} | Details: {highlights}"
            )

        # 4. Professional Work Experiences
        for exp in profile.get("experiences", []):
            company = exp.get("company", "")
            role = exp.get("role", "")
            tech = ", ".join(exp.get("technologies", []))
            highlights = " ".join(exp.get("highlights", []))
            sections.append(
                f"Experience: {role} at {company} | Stack: {tech} | Impact: {highlights}"
            )

        return "\n".join(sections)

    def load_cache_jobs(self, cache_dir: str = "data/cache") -> List[Dict[str, Any]]:
        """
        Streams all compressed .json.gz chunk files into in-memory job dictionaries.
        """
        all_jobs = []
        manifest_path = os.path.join(cache_dir, "manifest.json")

        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            chunks = manifest.get("chunks", [])
            for chunk_file in chunks:
                c_path = os.path.join(cache_dir, chunk_file)
                if os.path.exists(c_path):
                    with gzip.open(c_path, "rt", encoding="utf-8") as gz:
                        all_jobs.extend(json.load(gz))
        else:
            # Fallback: scan folder for any .json.gz directly
            if os.path.exists(cache_dir):
                for fname in sorted(os.listdir(cache_dir)):
                    if fname.endswith(".json.gz"):
                        c_path = os.path.join(cache_dir, fname)
                        with gzip.open(c_path, "rt", encoding="utf-8") as gz:
                            all_jobs.extend(json.load(gz))

        return all_jobs

    def score_jobs(
        self,
        profile_text: str,
        jobs: List[Dict[str, Any]],
        threshold: float = 0.60,
        top_k: int = 25,
        batch_size: int = 128
    ) -> List[Dict[str, Any]]:
        """
        Computes Cosine Similarity between the candidate profile and in-memory jobs.
        Uses vectorized NumPy matrix operations for millisecond execution.
        """
        if not jobs:
            return []

        start_time = time.time()

        # 1. Embed profile vector and normalize
        profile_embed_gen = self.model.embed([profile_text])
        profile_vec = np.array(list(profile_embed_gen)[0], dtype=np.float32)
        norm_p = np.linalg.norm(profile_vec)
        if norm_p > 0:
            profile_vec = profile_vec / norm_p

        # 2. Extract job search signatures
        job_texts = []
        for j in jobs:
            title = j.get("title", "")
            company = j.get("company", "")
            location = j.get("location", "")
            desc = (j.get("description") or "")[:450]  # First 450 chars contain primary requirements
            job_texts.append(f"Position: {title} | Company: {company} | Location: {location} | Scope: {desc}")

        # 3. Batch embed job descriptions
        job_embeddings_gen = self.model.embed(job_texts, batch_size=batch_size)
        job_matrix = np.array(list(job_embeddings_gen), dtype=np.float32)

        # 4. Normalize matrix rows
        row_norms = np.linalg.norm(job_matrix, axis=1, keepdims=True)
        row_norms[row_norms == 0] = 1.0
        job_matrix_norm = job_matrix / row_norms

        # 5. Vectorized Dot Product = Cosine Similarity
        scores = np.dot(job_matrix_norm, profile_vec)

        # 6. Filter by threshold and format output
        matched_jobs = []
        for idx, score in enumerate(scores):
            score_val = round(float(score), 4)
            if score_val >= threshold:
                item = dict(jobs[idx])
                item["match_score"] = score_val
                item["match_percentage"] = int(score_val * 100)
                matched_jobs.append(item)

        # Sort descending by match score
        matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        elapsed = time.time() - start_time
        print(f"[VectorMatcher] Evaluated {len(jobs)} jobs in {elapsed:.3f}s. Qualifying matches: {len(matched_jobs)}")

        return matched_jobs[:top_k]