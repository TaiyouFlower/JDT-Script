from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import io
import os
import uuid
import webp 
import re
import logging
import requests

app = FastAPI()

static_dir = "static"
subfolders = ["600x600-jpg", "600x600-webp", "1200x1200-jpg", "1200x1200-webp"]

# Ensure the 'static' folder exists
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Create the subfolders inside 'static'
for folder in subfolders:
    path = os.path.join(static_dir, folder)
    if not os.path.exists(path):
        os.makedirs(path)



app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend URL if specific
    allow_methods=["GET", "POST", "OPTIONS"],  # Include "OPTIONS"
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("uvicorn")

# Define input schema
class InputText(BaseModel):
    text: str
    
def normalize_text(text: str) -> str:
    """Replaces multiple consecutive line breaks with a single line break
    and multiple spaces in a row with a single space within lines.
    """
    text = re.sub(r'\n+', '\n', text.strip())  # Normalize multiple line breaks
    text = re.sub(r' +', ' ', text)  # Normalize multiple spaces
    text = re.sub(r'(?m)^\s*\n+', '\n', text) # Remove multiple vertical-only spaces
    return text

def parse_text_to_sections(text):
    """
    Parse the input plain text into sections based on patterns.
    """
    sections = {}
    try:
        # Extract Title
        title_match = re.search(r"^(.+?)\n", text)
        sections["title"] = title_match.group(1).strip() if title_match else "No Title"

        # Extract Position by removing "Job Description Template"
        if "Job Description Template" in sections["title"]:
            sections["position"] = sections["title"].replace("Job Description Template", "").strip()
        else:
            sections["position"] = sections["title"]


        # Extract Template Overview 
        template_match = re.search(r"Template Overview\n(.+?)(\n(?:Introduction))", text, re.DOTALL | re.IGNORECASE)
        if template_match:
            sections["template_overview"] =f"<h3>Template Overview</h3>\n" + template_match.group(1).strip() 
        else:
            sections["template_overview"] = ""


        # Extract Introduction 
        Introduction_match = re.search(r"Introduction\n(.+?)(\n(?:What does|General overview))", text, re.DOTALL | re.IGNORECASE)
        if Introduction_match:
            sections["introduction"] = f"<h3>Introduction</h3>\n" + Introduction_match.group(1).strip()
        else:
            sections["introduction"] = ""

        
        # Extract What is a [job_name] job description template 
        whatIs_match = re.search(fr"What is a {sections['position']} job description template\?\n(.+?)(\n(?:General overview))", text, re.DOTALL | re.IGNORECASE)
        if whatIs_match:
            sections["what_is"] = f"<h3>What is a {sections['position']} job description template</h3>?\n" + whatIs_match.group(1).strip()
        else:
            sections["what_is"] = ""
        
        # Extract What is an [job_name] job description template 
        whatIs_match_an = re.search(fr"What is an {sections['position']} job description template\?\n(.+?)(\n(?:General overview))", text, re.DOTALL | re.IGNORECASE)
        if whatIs_match_an:
            sections["what_is_an"] = f"<h3>What is an {sections['position']} job description template</h3>?\n" + whatIs_match_an.group(1).strip()
        else:
            sections["what_is_an"] = ""


        # Extract General Overview
        general_match = re.search(r"General overview of the role\n(.+?)(\n(?:Typical Duties|Typical duties|What does))", text, re.DOTALL | re.IGNORECASE)
        if general_match:
            sections["general_overview"] = f"<h3>General overview of the role</h3>\n" + general_match.group(1).strip()
        else:
            sections["general_overview"] = ""


        # Extract what does a [job] do 
        whatDoes_match = re.search(fr"What does a {sections['position']} do\?\n(.+?)(\n(?:Typical Duties|Typical duties|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if whatDoes_match:
            sections["what_does_title"] =f"<h3> What does a {sections['position']} do?</h3>\n"
            sections["what_does_begin"] ="<ul>"
            sections["what_does_end"] = "</ul>"
            sections["what_does"] = [duty.strip() for duty in whatDoes_match.group(1).split("\n") if duty.strip()]
        else:
            sections["what_does_title"] = ""
            sections["what_does_begin"] =""
            sections["what_does_end"] = ""
            sections["what_does"] = []
            
            
        # Extract what does an [job] do 
        whatDoes_match_an = re.search(fr"What does an {sections['position']} do\?\n(.+?)(\n(?:Typical Duties|Typical duties|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if whatDoes_match_an:
            sections["what_does_title_an"] =f"<h3> What does an {sections['position']} do?</h3>\n"
            sections["what_does_begin_an"] ="<ul>"
            sections["what_does_end_an"] = "</ul>"
            sections["what_does_an"] = [duty.strip() for duty in whatDoes_match.group(1).split("\n") if duty.strip()]
        else:
            sections["what_does_title_an"] = ""
            sections["what_does_begin_an"] =""
            sections["what_does_end_an"] = ""
            sections["what_does_an"] = []
        
        # Extract what does an [job] do 
        whatDoes_match_an = re.search(fr"What does an {sections['position']} do\?\n(.+?)(\n(?:Typical Duties|Typical duties|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if not whatDoes_match_an:
            whatDoes_match_an = re.search(r"do?\n(.+?)(\n(?:Required skills | Required Skills))", text, re.DOTALL | re.IGNORECASE)
        if whatDoes_match_an:
            sections["what_does_title_an"] =f"<h3> What does an {sections['position']} do?</h3>\n"
        else:
            sections["what_does_title_an"] = ""
        

        # Extract Duties
        duties_match = re.search(r"Typical Duties and Responsibilities:\n(.+?)(\n(?:Required Skills|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if not duties_match:
            # Try alternative case-insensitive heading
            duties_match = re.search(r"Typical duties and responsibilities\n(.+?)(\n(?:Required Skills|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if duties_match:
            sections['duties_begin'] = "<ul>"
            sections['duties_end'] = "</ul>"
            sections['duties_title'] = "<h3 class='include'>Typical duties and responsibilities</h3>"
            sections["duties"] = [duty.strip() for duty in duties_match.group(1).split("\n") if duty.strip()]
        else:
            sections["duties"] = []
            sections['duties_begin'] = ""
            sections['duties_end'] = ""
            sections['duties_title'] = ""

        # Extract Required Skills
        skills_match = re.search(r"Required Skills and Experience:\n(.+?)(\n(?:Nice to Have|Nice to have))", text, re.DOTALL | re.IGNORECASE)
        if not skills_match:
            # Try alternative case-insensitive heading
            skills_match = re.search(r"Required skills and experience\n(.+?)(\n(?:Nice to Have|Nice to have))", text, re.DOTALL | re.IGNORECASE)
        if skills_match:
            sections["required_skills"] = [skill.strip() for skill in skills_match.group(1).split("\n") if skill.strip()]
        else:
            sections["required_skills"] = []

        # Extract Nice to Have
        nice_to_have_match = re.search(r"Nice to Have/Preferred Skills and Experience:\n(.+?)(\n(?:" + sections['position'] + r" Salary Breakdown|What are the key|Common challenges faced by|Common mistakes to avoid|What we offer|Explore sample resumes))", text, re.DOTALL | re.IGNORECASE)
        if not nice_to_have_match:
            # Try alternative 
            nice_to_have_match = re.search(r"Nice to have/preferred skills and experience \(not required\)\n(.+?)(\n(?:" + sections['position'] + r" Salary Breakdown|What are the key|Common challenges faced by|Common mistakes to avoid|What we offer|Explore sample resumes))", text, re.DOTALL | re.IGNORECASE)
            if not nice_to_have_match:
            # Try alternative 
                nice_to_have_match = re.search(r"Nice to have/preferred skills and experience\n(.+?)(\n(?:" + sections['position'] + r" Salary Breakdown|What are the key|Common challenges faced by|Common mistakes to avoid|What we offer|Explore sample resumes))", text, re.DOTALL | re.IGNORECASE)
        if nice_to_have_match:
            sections["nice_to_have"] = [item.strip() for item in nice_to_have_match.group(1).split("\n") if item.strip()]
        else:
            sections["nice_to_have"] = []
            
            
        # Extract what are the key [job_name] skills 
        key_match = re.search(r"What are the key", text, re.DOTALL | re.IGNORECASE)
        if key_match:
            sections["key_title"] = f"<h3>What are the key {sections['position']} skills?</h3>\n"
            sections["hard_title"] = f"<b>Hard skills</b>"
            sections["soft_title"] = f"<b>Soft skills</b>"
            sections["key_begin"] = "<ul>"
            sections["key_end"] = "</ul>"
        else:
            sections["key_title"] = ""
            sections["hard_title"] = ""
            sections["soft_title"] = ""
            sections["key_begin"] = ""
            sections["key_end"] = ""
            
        # Extract hard skills
        hard_skills_match = re.search(r"Hard skills\n(.+?)(\n(?:Soft skills))", text, re.DOTALL | re.IGNORECASE)
        if  hard_skills_match:
            sections["hard_skills"] =[item.strip() for item in hard_skills_match.group(1).split("\n") if item.strip()]
        else:
            sections["hard_skills"] = []
            
        # Extract soft skills
        soft_skills_match = re.search(r"Soft skills\n(.+?)(\n(?:" + sections['position'] + r" salary))", text, re.DOTALL | re.IGNORECASE)
        if soft_skills_match:
            sections["soft_skills"] =[item.strip() for item in soft_skills_match.group(1).split("\n") if item.strip()]
        else:
            sections["soft_skills"] = []

        # Extract mistakes to avoid 
        common_mistakes_match = re.search(fr"Common mistakes to avoid when creating a {sections['position']} job description\n(.+?)(\n(?:What we offer))", text, re.DOTALL | re.IGNORECASE)
        if common_mistakes_match:
            sections["common_mistakes_title"] = f"<h3>Common mistakes to avoid when creating a {sections['position']} job description</h3>\n"
            sections["common_mistakes_begin"] = "<ul>"
            sections["common_mistakes_end"] = "</ul>"
            sections["common_mistakes_avoid"] =[item.strip() for item in common_mistakes_match.group(1).split("\n") if item.strip()]
        else:
            sections["common_mistakes_title"]=""
            sections["common_mistakes_begin"] = ""
            sections["common_mistakes_end"] = ""
            sections["common_mistakes_avoid"] = []
            
        common_mistakes_match_an = re.search(fr"Common mistakes to avoid when creating an {sections['position']} job description\n(.+?)(\n(?:What we offer))", text, re.DOTALL | re.IGNORECASE)
        if common_mistakes_match_an:
            sections["common_mistakes_title_an"] = f"<h3>Common mistakes to avoid when creating an {sections['position']} job description</h3>\n"
            sections["common_mistakes_begin_an"] = "<ul>"
            sections["common_mistakes_end_an"] = "</ul>"
            sections["common_mistakes_avoid_an"] =[item.strip() for item in common_mistakes_match_an.group(1).split("\n") if item.strip()]
        else:
            sections["common_mistakes_title_an"]=""
            sections["common_mistakes_begin_an"] = ""
            sections["common_mistakes_end_an"] = ""
            sections["common_mistakes_avoid_an"] = []

        # Extract Salary Breakdown
        salary_breakdown_match = re.search(fr"{sections['position']} salary breakdown\n(.+?)(\n(?:Common challenges faced by|What we offer))", text, re.DOTALL | re.IGNORECASE)
        if salary_breakdown_match:
            sections["salary_breakdown"] = f"<h3>{sections['position']} salary breakdown</h3>\n" + salary_breakdown_match.group(1).strip()
        else:
            sections["salary_breakdown"] = ""
            
        # Extract Salary 
        salary_match = re.search(fr"and location\:\n(.+?)(\n(?:How can I))", text, re.DOTALL | re.IGNORECASE)
        if salary_match:
            sections["salary_title"] = f"<h3>{sections['position']} salary </h3>\n"
            sections["salary_begin"]  = "<ul>"
            sections["salary_end"] = "</ul>"
            sections["salary_mini"] = f"Salaries for {sections['position']} vary based on experience, industry, and location:"
            sections["salary"] = [item.strip() for item in salary_match.group(1).split("\n") if item.strip()]
        else:
            sections["salary_title"] = ""
            sections["salary_begin"] = ""
            sections["salary_end"] = ""
            sections["salary_mini"] = ""
            sections["salary"] = []
            
        # Extract how can I become a good [job_name]
        can_match = re.search(fr"How can I become a good {sections['position']}\?\n(.+?)(\n(?:Why join us))", text, re.DOTALL | re.IGNORECASE)
        if can_match:
            sections["can_title"] = f"<h3>How can I become a good {sections['position']}</h3>\n" 
            sections["can_begin"] = "<ul>"
            sections["can_end"] = "</ul>"
            sections["can"] =[item.strip() for item in can_match.group(1).split("\n") if item.strip()]
        else:   
            sections["can_title"] = ""
            sections["can_begin"] = ""
            sections["can_end"] = ""
            sections["can"] = []
            
        # Extract why join us as [job_name]
        why_match = re.search(fr"Why join us as {sections['position']}\?\n(.+?)(\n(?:What we offer))", text, re.DOTALL | re.IGNORECASE)
        if why_match:
            sections["why_title"] = f"<h3>Why join us as {sections['position']}</h3>\n" 
            sections["why_begin"] = "<ul>"
            sections["why_end"] = "</ul>"
            sections["why"] =[item.strip() for item in why_match.group(1).split("\n") if item.strip()]
        else:   
            sections["why_title"] = ""
            sections["why_begin"] = ""
            sections["why_end"] = ""
            sections["why"] = []
        
        # Extract Common challenges
        challenges_match = re.search(fr"Common challenges faced by {sections['position']}s\n(.+?)(\n(?:Where do|What we))", text, re.DOTALL | re.IGNORECASE)
        if challenges_match:
            sections["challenge_title"] = f"<h3>Common challenges faced by {sections['position']}s</h3>\n"
            sections["challenge_begin"] = "<ul>"
            sections["challenge_end"] = "</ul>"
            sections["common_challenges"] =[item.strip() for item in challenges_match.group(1).split("\n") if item.strip()]
        else:
            sections["challenge_title"]=""
            sections["challenge_begin"] = ""
            sections["challenge_end"] = ""
            sections["common_challenges"] = []

        
        # Extract where do [job_name]s work
        where_match = re.search(fr"Where do {sections['position']}s work\?\n(.+?)(\n(?:How can I))", text, re.DOTALL | re.IGNORECASE)
        if where_match:
            sections["where_do"] = f"<h3>Where do {sections['position']}s work?</h3>\n" + where_match.group(1) .strip()
        else:
            sections["where_do"] = ""



        # Extract How can I be a good [job_name]
        how_match = re.search(fr"How can I be a good {sections['position']}\?\n(.+?)(\n(?:Mistakes to))", text, re.DOTALL | re.IGNORECASE)
        if how_match:
            sections["how_can"] = f"<h3>How can I be a good {sections['position']}</h3>\n" + how_match.group(1) .strip()
        else:   
            sections["how_can"] = ""
            
        # Extract How can I be an good [job_name]
        how_match_an = re.search(fr"How can I be an good {sections['position']}\?\n(.+?)(\n(?:Mistakes to))", text, re.DOTALL | re.IGNORECASE)
        if how_match_an:
            sections["how_can_an"] = f"<h3>How can I be an good {sections['position']}</h3>\n  " + how_match_an.group(1) .strip()
        else:   
            sections["how_can_an"] = ""

        
        # Extract mistakes to avoid 
        mistakes_match = re.search(fr"Mistakes to avoid as a {sections['position']}\n(.+?)(\n(?:What we offer))", text, re.DOTALL | re.IGNORECASE)
        if mistakes_match:
            sections["mistakes_title"] = f"<h3>Mistakes to avoid as a {sections['position']}</h3>\n"
            sections["mistakes_begin"] = "<ul>"
            sections["mistakes_end"] = "</ul>"
            sections["mistakes_avoid"] =[item.strip() for item in mistakes_match.group(1).split("\n") if item.strip()]
        else:
            sections["mistakes_title"]=""
            sections["mistakes_begin"] = ""
            sections["mistakes_end"] = ""
            sections["mistakes_avoid"] = []
        
        # Extract mistakes to avoid (an)   
        mistakes_match_an = re.search(fr"Mistakes to avoid as an {sections['position']}\n(.+?)(\n(?:What we offer))", text, re.DOTALL | re.IGNORECASE)
        if mistakes_match_an:
            sections["mistakes_title_an"] = f"<h3>Mistakes to avoid as an {sections['position']}</h3>\n"
            sections["mistakes_begin_an"] = "<ul>"
            sections["mistakes_end_an"] = "</ul>"
            sections["mistakes_avoid_an"] =[item.strip() for item in mistakes_match_an.group(1).split("\n") if item.strip()]
        else:
            sections["mistakes_title_an"]=""
            sections["mistakes_begin_an"] = ""
            sections["mistakes_end_an"] = ""
            sections["mistakes_avoid_an"] = []

        

        # Extract resumes
        resume_match = re.search(r"Explore these effective resume examples to guide your focus and priorities during the candidate review.\n(.+?)(\nContact DevsData LLC)", text, re.DOTALL | re.IGNORECASE)
        if not resume_match:
            # Try alternative case-insensitive heading
            resume_match = re.search(r"Explore these resume examples to guide your focus and priorities during the candidate review\n(.+?)(\n(\nContact DevsData LLC))", text, re.DOTALL | re.IGNORECASE)
            if not resume_match:
                resume_match = re.search(r"Explore these resume examples to guide your focus and priorities during the candidate review:\n(.+?)(\n(\nContact DevsData LLC))", text, re.DOTALL | re.IGNORECASE) 
                if not resume_match:
                    resume_match = re.search(r"Explore these effective resume examples to guide your focus and priorities during the candidate review:\n(.+?)(\n(\nContact DevsData LLC))", text, re.DOTALL | re.IGNORECASE)
        if resume_match:
            sections["resumes"] = [resume.strip() for resume in resume_match.group(1).split("\n") if resume.strip()]
        else:
            sections["resumes"] = []
            
        # Extract FAQ 
        faq_match = re.search(r"FAQ", text, re.DOTALL | re.IGNORECASE)
        if faq_match:
            sections["faq1"] = f'<script>\nconst faq = {{\n "Question 1": {{\n "Answer": "Answer1"'
            sections["faq2"] = f'}},\n"Question 2": {{\n "Answer": "Answer2"'
            sections["faq3"] = f'}},\n"Question 3": {{\n "Answer": "Answer3"'
            sections["faq4"] = f'}},\n}}\n</script>\n[faq]'
        else:
            sections["faq1"] = ""
            sections["faq2"] = ""
            sections["faq3"] = ""
            sections["faq4"] = ""
        

    except Exception as e:
        logger.exception("Error parsing text to sections:")
        raise HTTPException(status_code=500, detail=str(e))

    return sections

def generate_wordpress_code(sections):
    """
    Generate WordPress-formatted HTML from parsed sections.
    """
    try:
        # Static parts of the template
        wordpress_template = f"""
<section>

<h1> {sections['title']} </h1>

[post_info]

[image src='2025/02/{sections['position'].replace(' ', '_')}_JDT' alt='{sections['position']} working']

{sections['template_overview']}

{sections['what_is']}
{sections['what_is_an']}

{sections['introduction']}

{sections['general_overview']}

{sections['what_does_title']} 
{sections['what_does_begin']} 
{sections['what_does_title_an']}
{sections['what_does_begin_an']}  
"""
        for item in sections["what_does"]:
            wordpress_template += f"  <li>{item}</li>\n"
        for item in sections["what_does_an"]:
            wordpress_template += f"  <li>{item}</li>\n"    
        wordpress_template += f"""
{sections['what_does_end']} 
{sections['what_does_end_an']}  
{sections['duties_title']}
{sections['duties_begin']}
"""
        for duty in sections["duties"]:
            wordpress_template += f"  <li>{duty}</li>\n"
        wordpress_template += f"{sections['duties_end']}"
        wordpress_template += "\n<h3 class='include'>Required skills and experience</h3>\n<ul style='margin-bottom: 30px;'>\n"
        for skill in sections["required_skills"]:
            wordpress_template += f"  <li>{skill}</li>\n"

        wordpress_template += "</ul>\n\n[scheduler text='IT recruitment']\n\n<h3>Nice to have/preferred skills and experience (not required)</h3>\n<ul>\n"
        for item in sections["nice_to_have"]:
            wordpress_template += f"  <li>{item}</li>\n"
            
        wordpress_template += f"""
</ul>
{sections['key_title']}
{sections['hard_title']}
{sections['key_begin']}
        """            
        for item in sections["hard_skills"]:
            wordpress_template += f"  <li>{item}</li>\n"
        wordpress_template += f"""
{sections['key_end']}
{sections['soft_title']}
{sections['key_begin']}
        """ 
        for item in sections["soft_skills"]:
            wordpress_template += f"  <li>{item}</li>\n"  
        wordpress_template += f"""{sections['key_end']}
{sections['salary_title']}
{sections['salary_mini']}
{sections['salary_begin']}
        """
        for item in sections["salary"]:
            wordpress_template += f"  <li>{item}</li>\n"  
        wordpress_template += f"""
{sections['salary_end']}   
{sections['can_title']}
{sections['can_begin']} 
        """    
        for item in sections["can"]:
            wordpress_template += f"  <li>{item}</li>\n"  
        wordpress_template += f"""
{sections['can_end']}
{sections['why_title']}
{sections['why_begin']}
        """
        for item in sections["why"]:
            wordpress_template += f"  <li>{item}</li>\n"  
        wordpress_template += f"""
{sections['salary_breakdown']}
{sections['challenge_title']}
{sections['challenge_begin']}
"""
        for challenge in sections["common_challenges"]:
            wordpress_template += f"  <li>{challenge}</li>\n "

        wordpress_template += f"""{sections['challenge_end']}
    
{sections['where_do']}

{sections['how_can']}
{sections['how_can_an']}

{sections['mistakes_title']}
{sections['mistakes_title_an']}
{sections['mistakes_begin']}
{sections['mistakes_begin_an']}
"""

        for mistake in sections["mistakes_avoid"]:
            wordpress_template += f"  <li>{mistake}</li>\n "
        
        for mistake in sections["mistakes_avoid_an"]:
            wordpress_template += f"  <li>{mistake}</li>\n "

        wordpress_template += f""" 
{sections['mistakes_end']}
{sections['mistakes_end_an']}

{sections['common_mistakes_title']}
{sections['common_mistakes_begin']}
{sections['common_mistakes_title_an']}
{sections['common_mistakes_begin_an']}
"""

        for common_mistake in sections["common_mistakes_avoid"]:
            wordpress_template += f"  <li>{common_mistake}</li>\n "

        wordpress_template += f""" {sections['common_mistakes_end']}
        """
        
        for common_mistake in sections["common_mistakes_avoid_an"]:
            wordpress_template += f"  <li>{common_mistake}</li>\n "

        wordpress_template += f""" {sections['common_mistakes_end_an']}

<h3 class='include'>What we offer</h3>

<ul>
    <li>Extensive health and wellness coverage.</li>
    <li>Work-from-home options and flexible hours.</li>
    <li>Paid time off for vacations, holidays, and sick leave.</li>
</ul>

<i>Here are a few more benefits that, according to <a href="https://www.forbes.com/sites/carolinecastrillon/2022/10/02/top-ten-most-valued-employee-benefits/" target="_blank" rel="nofollow noreferrer noopener">Forbes</a>, are valued by employees:</i>

<ul>
    <li>Retirement savings plans with employer matching, such as 401(k) plans, are highly valued by employees.</li>
    <li>Early leave on Fridays.</li>
    <li>4-day work week.</li>
    <li>Private dental insurance.</li>
</ul>

<h3 class='include'>About us</h3>

We recommend including general information about the company, such as its mission, values, and industry focus. For instance, you could say:

<i>&quot;DevsData LLC is an <a href="/recruitment" target="_blank" rel="noopener">IT recruitment agency</a> that connects top tech talent with leading companies to drive innovation and success. Their diverse team of US specialists brings unique viewpoints and cultural insights, boosting their capacity to meet client demands and build inclusive work cultures. Over the past 8 years, DevsData LLC has successfully completed more than 80 projects for startups and corporate clients in the US and Europe.&quot;</i>

<h3 class='include'>Explore sample resumes</h3>

Explore these effective resume examples to guide your focus and priorities during the candidate review.

<ul>
        """
        for resume in sections["resumes"]:
            wordpress_template += f"  <li><a href='/resumes/{resume.lower().replace(' ', '-')}/' target='_blank'>{resume}</a></li>\n"

        wordpress_template += f"""
</ul>

<h3 class='include'>Contact DevsData LLC</h3>

If you're looking to hire a qualified {sections['position']}, reach out to DevsData LLC at <a href="mailto:general@devsdata.com">general@devsdata.com</a> or visit <a href="/" target="_blank" rel="noopener">www.devsdata.com</a>. The company's recruitment process is thorough and efficient, utilizing a vast database of over <span class="formatted-number">65000</span> professionals.

They are renowned for their rigorous 90-minute interviews to assess candidates' technical skills and problem-solving abilities.

Additionally, DevsData LLC holds a government-approved recruitment license, ensuring compliance with industry standards and regulations.

[copy_btn]

</section>
"""

        wordpress_template += """
<style>
    ul li a:hover, ol li a:hover{
        text-decoration: underline;
        cursor: pointer;
    }
</style>
[post_author_info]
"""
        wordpress_template +=f"""
{sections['faq1']}
{sections['faq2']}
{sections['faq3']}
{sections['faq4']}
"""
        return normalize_text(wordpress_template)

    except Exception as e:
        logger.exception("Error generating WordPress code:")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/generate/")
async def generate_html(input_text: InputText):
    try:
        sections = parse_text_to_sections(input_text.text)
        wordpress_code = generate_wordpress_code(sections)
        return {"wordpress_code": wordpress_code}
    except Exception as e:
        logger.exception("Error while generating HTML:")
        raise HTTPException(status_code=500, detail="Internal Server Error")


os.makedirs('static/1200x1200-jpg', exist_ok=True)
os.makedirs('static/1200x1200-webp', exist_ok=True)
os.makedirs('static/600x600-jpg', exist_ok=True)
os.makedirs('static/600x600-webp', exist_ok=True)

def resize_image(image, max_size):
    """ Resize the image while maintaining its aspect ratio """
    image.thumbnail(max_size)  # Resize while keeping aspect ratio
    return image

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        unique_filename = f"{uuid.uuid4()}_{file.filename.rsplit('.', 1)[0]}"
        real_filename = file.filename.rsplit('.', 1)[0];
        image_data = await file.read()
        original_image = Image.open(io.BytesIO(image_data))

        # Define max sizes while maintaining aspect ratio
        sizes = {
            "1200x1200-jpg": (1200, 1200),
            "1200x1200-webp": (1200, 1200),
            "600x600-jpg": (600, 600),
            "600x600-webp": (600, 600)
        }

        compressed_images = {}

        for size_name, max_size in sizes.items():
            resized_img = resize_image(original_image.copy(), max_size).convert("RGB")
            
            file_extension = "jpg" if "jpg" in size_name else "webp"
            if max_size==(1200,1200):
                final_filename = f"{real_filename}.{file_extension}"
            else:
                final_filename = f"{real_filename}_small.{file_extension}"
            file_path = os.path.join("static", size_name, final_filename)

            if file_extension == "jpg":
                resized_img.save(file_path, format="JPEG", quality=100)
            else:
                resized_img.save(file_path, format="WEBP", quality=100)
            
            compressed_images[size_name] = f"https://jdt-script.up.railway.app/static/{size_name}/{final_filename}"
        
        return {"status_code": 200, "message": "Images uploaded and processed successfully!", "compressedImages": compressed_images}
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing image")

@app.get("/download/{size}/{filename}")
def download_image(size: str, filename: str):
    file_path = os.path.join("static", size, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, headers={"Content-Disposition": "attachment; filename=\"{}\"".format(filename)})
    raise HTTPException(status_code=404, detail="File not found")

