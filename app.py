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

        # Extract General Overview
        general_match = re.search(r"General overview of the role\n(.+?)(\n(?:Typical Duties|Typical duties))", text, re.DOTALL | re.IGNORECASE)
        if not general_match:
            general_match = re.search(r"Introduction\n(.+?)(\n(?:Typical Duties|Typical duties))", text, re.DOTALL | re.IGNORECASE)
            if not general_match: 
                general_match = re.search(r"General overview of the role:\n(.+?)(\n(?:Typical Duties|Typical duties))", text, re.DOTALL | re.IGNORECASE)
        sections["general_overview"] = general_match.group(1).strip() if general_match else ""

        # Extract Duties
        duties_match = re.search(r"Typical Duties and Responsibilities:\n(.+?)(\n(?:Required Skills|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if not duties_match:
            # Try alternative case-insensitive heading
            duties_match = re.search(r"Typical duties and responsibilities\n(.+?)(\n(?:Required Skills|Required skills))", text, re.DOTALL | re.IGNORECASE)
        if duties_match:
            sections["duties"] = [duty.strip() for duty in duties_match.group(1).split("\n") if duty.strip()]
        else:
            sections["duties"] = []

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
        nice_to_have_match = re.search(r"Nice to Have/Preferred Skills and Experience:\n(.+?)(\n(?:What we offer|Explore sample resumes))", text, re.DOTALL | re.IGNORECASE)
        if not nice_to_have_match:
            # Try alternative case-insensitive heading
            nice_to_have_match = re.search(r"Nice to have/preferred skills and experience (not required)\n(.+?)(\n(?:What we offer|Explore sample resumes))", text, re.DOTALL | re.IGNORECASE)
            if not nice_to_have_match:
            # Try alternative case-insensitive heading
                nice_to_have_match = re.search(r"Nice to have/preferred skills and experience\n(.+?)(\n(?:What we offer|Explore sample resumes))", text, re.DOTALL | re.IGNORECASE)
        if nice_to_have_match:
            sections["nice_to_have"] = [item.strip() for item in nice_to_have_match.group(1).split("\n") if item.strip()]
        else:
            sections["nice_to_have"] = []

        # Add resumes list (example)
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

<h3>General overview of the role</h3>\n
{sections['general_overview']}

<h3 class='include'>Typical duties and responsibilities</h3>\n
<ul>
"""
        for duty in sections["duties"]:
            wordpress_template += f"  <li>{duty}</li>\n "

        wordpress_template += "</ul>\n\n<h3>Required skills and experience</h3>\n\n<ul style='margin-bottom: 30px;'>\n"
        for skill in sections["required_skills"]:
            wordpress_template += f"  <li>{skill}</li>\n"

        wordpress_template += "</ul>\n\n[scheduler text='IT recruitment']\n\n<h3 class='include'>Nice to have/preferred skills and experience (not required)</h3>\n\n<ul>\n"
        for item in sections["nice_to_have"]:
            wordpress_template += f"  <li>{item}</li>\n"
        wordpress_template += """
</ul>

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

<i>&quot;DevsData LLC is an <a href="https://devsdata.com/recruitment/" target="_blank" rel="noopener">IT recruitment agency</a> that connects top tech talent with leading companies to drive innovation and success. Their diverse team of US specialists brings unique viewpoints and cultural insights, boosting their capacity to meet client demands and build inclusive work cultures. Over the past 8 years, DevsData LLC has successfully completed more than 80 projects for startups and corporate clients in the US and Europe.&quot;</i>

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

        return wordpress_template

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

