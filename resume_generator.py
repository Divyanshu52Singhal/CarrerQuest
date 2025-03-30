import jinja2
from input_sanitizer import sanitize_latex_input
from info_formatters import InfoFormatters 
class ResumeGenerator:
    def __init__(self, template_file="resume_template.tex"):
        """Initialize the resume generator with a LaTeX template file."""
        self.template_file = template_file
        
        # Set up a Jinja2 environment with LaTeX-friendly delimiters
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader("."),
            variable_start_string='{{ ',
            variable_end_string=' }}',
            comment_start_string='{# ',
            comment_end_string=' #}',
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False  # Don't escape LaTeX special characters
        )

    def generate_resume(self, data):
        """
        Generate LaTeX resume from data.
        
        Args:
            data: Dictionary containing resume data
            output_filename: Base name for output files (without extension)
        
        Returns:
            Tuple of (latex_path, pdf_path)
        """
        # print(type(data))
        data = sanitize_latex_input(data)
        # Process template placeholders
        context = {
            "full_name": data.get("name", "Your Name"),
            "phone": data.get("phone", "123-456-7890"),
            "email": data.get("email", "youremail@example.com"),
            "linkedin_url": data.get("linkedin_url", "https://linkedin.com/in/..."),
            "linkedin_display": data.get("linkedin_display", "linkedin.com/in/..."),
            "github_url": data.get("github_url", "https://github.com/..."),
            "github_display": data.get("github_display", "github.com/..."),
            "education_entries": InfoFormatters.format_education(data.get("education", [])),
            "experience_entries": InfoFormatters.format_experience(data.get("experience", [])),
            "project_entries": InfoFormatters.format_projects(data.get("projects", [])),
            "skills_entries": InfoFormatters.format_skills(data.get("skills", {})),
            "additional_sections": InfoFormatters.format_additional_sections(data.get("additional_sections", {}))
        }
        

        # Generate LaTeX document
        template = self.env.get_template(self.template_file)
        return template.render(**context)
        
        # # Save LaTeX file
        # latex_path = f"{output_filename}.tex"
        # with open(latex_path, "w", encoding="utf-8") as f:
        #     f.write(latex_content)
        
        # print(f"LaTeX file generated: {latex_path}")
            
        # Compile to PDF
        # pdf_path = f"{output_filename}.pdf"
        # try:
            # Run pdflatex twice to generate proper references
            # subprocess.run(["pdflatex", latex_path], check=True, stdout=subprocess.PIPE)
            # subprocess.run(["pdflatex", latex_path], check=True, stdout=subprocess.PIPE)
            
            # Clean up auxiliary files
            # for ext in [".aux", ".log", ".out"]:
            #     if os.path.exists(f"{output_filename}{ext}"):
            #         os.remove(f"{output_filename}{ext}")
                    
            # print(f"PDF generated: {pdf_path}")
        # return latex_path
            
        # except subprocess.CalledProcessError as e:
        #     print(f"Error generating PDF: {e}")
        #     return latex_path, None
        # except FileNotFoundError:
        #     print("pdflatex command not found. Make sure you have LaTeX installed.")
        #     return latex_path, None

    @classmethod
    def from_json(cls, json_data, template_file="resume_template.tex"):
        """
        Generate resume from JSON data file.
        
        Args:
            json_file: Path to JSON file with resume data
            template_file: Path to LaTeX template
            output_filename: Base name for output files
            
        Returns:
            Tuple of (latex_path, pdf_path)
        """
        try:
            generator = cls(template_file)
            return generator.generate_resume(json_data)
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return None, None


# if __name__ == "__main__":
#     import argparse
    
#     parser = argparse.ArgumentParser(description="Generate a LaTeX resume from data file")
#     parser.add_argument("data_file", help="Path to YAML or JSON file containing resume data")
#     parser.add_argument("-t", "--template", default="resume_template.tex", help="Path to LaTeX template file")
#     parser.add_argument("-o", "--output", default="resume", help="Base name for output files (without extension)")
    
#     args = parser.parse_args()
    
#     file_ext = Path(args.data_file).suffix.lower()
    
#     if file_ext == ".json":
        
#     else:
#         print(f"Unsupported file format: {file_ext}")
#         print("Please provide a YAML or JSON file.")