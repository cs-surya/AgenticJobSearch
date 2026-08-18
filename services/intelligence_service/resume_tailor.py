import os
import json
import time
import re
import hashlib
import typst
from typing import Dict, Any, List
import ollama


class ResumeTailor:
    def __init__(self, model_name: str = "llama3.1"):
        self.model_name = model_name
        self.project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.output_dir = os.path.join(self.project_root, "data", "resumes")
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text: str) -> str:
        """Removes and escapes any characters that break Typst markup parsing."""
        if not text:
            return ""
        clean = str(text).replace('\\', '')
        clean = clean.replace('[', '(').replace(']', ')')
        clean = clean.replace('<', '(').replace('>', ')')
        clean = clean.replace('@', '')
        clean = clean.replace('#', '\\#').replace('$', '\\$').replace('*', '\\*').replace('_', '\\_')
        clean = clean.replace('\n', ' ').replace('\r', '')
        return clean.strip()

    def tailor_profile_with_llm(self, profile: Dict[str, Any], job: Dict[str, Any]) -> List[Dict[str, Any]]:
        job_title = job.get("title", "")
        company = job.get("company", "")
        job_desc = (job.get("description") or "")[:600]

        experiences = profile.get("experiences", [])
        target_exps = experiences[:2]

        prompt = f"""You are a technical ATS resume optimizer.
Target Job: {job_title} at {company}
Scope: {job_desc}

Candidate Roles to Optimize:
{json.dumps([{'company': e.get('company', ''), 'role': e.get('role', ''), 'highlights': e.get('highlights', [])} for e in target_exps], indent=2)}

Task:
Rephrase the bullet points for these 2 companies to emphasize technical alignment with the target job.
Keep the exact same number of bullet points per company.
Return ONLY valid JSON matching this structure:
{{
  "tailored_experiences": [
    {{
      "company": "BELL Canada",
      "highlights": ["...", "..."]
    }}
  ]
}}"""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 400,
                    "top_p": 0.9
                }
            )
            content = response["message"]["content"]
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return data.get("tailored_experiences", [])
        except Exception as e:
            print(f"[ResumeTailor] Fast fallback triggered: {e}")

        return []

    def generate_pdf(self, profile: Dict[str, Any], job: Dict[str, Any], use_llm: bool = True) -> str:
        start_time = time.time()

        # 1. Tailor highlights
        experiences = []
        if use_llm:
            tailored_list = self.tailor_profile_with_llm(profile, job)
            tailored_map = {str(t.get("company", "")).lower(): t.get("highlights", []) for t in tailored_list}
            for orig in profile.get("experiences", []):
                e = dict(orig)
                ckey = str(orig.get("company", "")).lower()
                if ckey in tailored_map and tailored_map[ckey]:
                    e["highlights"] = tailored_map[ckey]
                experiences.append(e)
        else:
            experiences = profile.get("experiences", [])

        personal = profile.get("personal", {})
        name = self._sanitize(personal.get("full_name", "SURYA CS"))
        phone = self._sanitize(personal.get("phone", ""))
        email = self._sanitize(personal.get("email", ""))
        website = self._sanitize(personal.get("website", ""))
        github = self._sanitize(personal.get("github", ""))
        linkedin = self._sanitize(personal.get("linkedin", ""))

        contact_1 = f"{phone} | {email}" if phone and email else f"{phone}{email}"
        links = [l for l in [website, github, linkedin] if l]
        contact_2 = " | ".join(links)

        # 2. Build Education Lines
        edu_lines = []
        for edu in profile.get("education", []):
            deg = self._sanitize(edu.get("degree", ""))
            dates = self._sanitize(edu.get("dates", ""))
            inst = self._sanitize(edu.get("institution", ""))
            edu_lines.append(f"*{deg}* #h(1fr) *{dates}* \\\n{inst}\n#v(0.35em)\n")
        edu_body = "".join(edu_lines)

        # 3. Build Experience Lines
        exp_lines = []
        for exp in experiences:
            role = self._sanitize(exp.get("role", ""))
            comp = self._sanitize(exp.get("company", ""))
            loc = self._sanitize(exp.get("location", ""))
            dates = self._sanitize(exp.get("dates", ""))

            bullet_rows = []
            for hl in exp.get("highlights", []):
                clean_hl = self._sanitize(hl)
                bullet_rows.append(f"- {clean_hl}\n")
            bullets_str = "".join(bullet_rows)

            exp_lines.append(f"*{role} -- {comp}* #h(1fr) *{dates}* \\\n_{loc}_\n#v(0.2em)\n{bullets_str}#v(0.35em)\n")
        exp_body = "".join(exp_lines)

        # 4. Build Project Lines
        proj_lines = []
        for proj in profile.get("projects", []):
            title = self._sanitize(proj.get("title", ""))
            bullet_rows = []
            for hl in proj.get("highlights", []):
                clean_hl = self._sanitize(hl)
                bullet_rows.append(f"- {clean_hl}\n")
            bullets_str = "".join(bullet_rows)
            proj_lines.append(f"*{title}* \\\n#v(-0.35em)\n{bullets_str}#v(0.35em)\n")
        proj_body = "".join(proj_lines)

        # 5. Assemble Pure Typst Markup
        typst_code = f"""
#set page(
  paper: "a4",
  margin: (x: 1.25cm, top: 1.1cm, bottom: 1.1cm)
)
#set text(
  font: ("Liberation Sans", "Helvetica", "Arial"),
  size: 9.2pt,
  fill: rgb("#000000")
)
#set par(justify: false, leading: 0.45em)
#set list(marker: ([●]), spacing: 0.55em)

#align(center)[
  #text(size: 16pt, weight: "bold")[{name}] \\
  #v(0.2em)
  #text(size: 9pt)[{contact_1}] \\
  #v(0.1em)
  #text(size: 9pt)[{contact_2}]
]

#v(0.4em)

#text(size: 10.5pt, weight: "bold")[EDUCATION]
#v(-0.55em)
#line(length: 100%, stroke: 0.75pt)
#v(0.15em)
{edu_body}
#v(0.2em)

#text(size: 10.5pt, weight: "bold")[WORK EXPERIENCE]
#v(-0.55em)
#line(length: 100%, stroke: 0.75pt)
#v(0.15em)
{exp_body}
#v(0.2em)

#text(size: 10.5pt, weight: "bold")[PROJECTS]
#v(-0.55em)
#line(length: 100%, stroke: 0.75pt)
#v(0.15em)
{proj_body}
"""

        raw_company = job.get('company') or "company"
        clean_company = re.sub(r'[^a-zA-Z0-9]', '', str(raw_company)).lower()[:12] or "company"
        unique_sig = f"{job.get('title', '')}_{job.get('apply_url', '')}"
        short_hash = hashlib.md5(unique_sig.encode()).hexdigest()[:6]

        base_name = f"resume_{clean_company}_{short_hash}"
        temp_typ_path = os.path.join(self.project_root, f".temp_{base_name}.typ")
        output_pdf_path = os.path.join(self.output_dir, f"{base_name}.pdf")

        with open(temp_typ_path, "w", encoding="utf-8") as f:
            f.write(typst_code)

        try:
            typst.compile(temp_typ_path, output=output_pdf_path)
        finally:
            if os.path.exists(temp_typ_path):
                os.remove(temp_typ_path)

        print(f"[ResumeTailor] Compiled ATS PDF in {time.time() - start_time:.3f}s -> {output_pdf_path}")
        return output_pdf_path