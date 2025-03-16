class InfoFormatters:
    @staticmethod
    def format_education(education_data):
        """Format education entries."""
        entries = []
        for edu in education_data:
            entries.append(
                f"\\resumeSubheading\n" +
                f"      {{{edu['institution']}}}{{{edu['location']}}}\n" +
                f"      {{{edu['degree']}}}{{{edu['duration']}}}\n"
            )
        return "\n    ".join(entries)
    
    @staticmethod
    def format_experience(experience_data):
        """Format experience entries with bullet points."""
        entries = []
        for exp in experience_data:
            entry = f"\\resumeSubheading\n" + \
                   f"      {{{exp['title']}}}{{{exp['duration']}}}\n" + \
                   f"      {{{exp['organization']}}}{{{exp['location']}}}\n" + \
                   f"      \\resumeItemListStart\n"
                   
            for bullet in exp['bullets']:
                entry += f"        \\resumeItem{{{bullet}}}\n"
                
            entry += "    \\resumeItemListEnd\n"
            entries.append(entry)
        return "\n".join(entries)
    
    @staticmethod
    def format_projects(projects_data):
        """Format project entries with bullet points."""
        entries = []
        for proj in projects_data:
            tech_stack = proj.get('technologies', '')
            tech_text = f" $|$ \\emph{{{tech_stack}}}" if tech_stack else ""
            
            entry = f"\\resumeProjectHeading\n" + \
                   f"          {{\\textbf{{{proj['name']}}}{tech_text}}}{{{proj['duration']}}}\n" + \
                   f"          \\resumeItemListStart\n"
                   
            for bullet in proj['bullets']:
                entry += f"            \\resumeItem{{{bullet}}}\n"
                
            entry += "          \\resumeItemListEnd\n"
            entries.append(entry)
        return "\n      ".join(entries)
        
    @staticmethod
    def format_skills(skills_data):
        """Format technical skills section."""
        entries = []
        for category, skills in skills_data.items():
            skills_str = ", ".join(skills)
            entries.append(f"\\textbf{{{category}}}{{: {skills_str}}}")
        
        return " \\\\\n     ".join(entries)
    
    @staticmethod
    def format_additional_sections(additional_sections):
        """Format any additional sections in the resume."""
        if not additional_sections:
            return ""
            
        sections = []
        for section_name, section_data in additional_sections.items():
            section = f"\\section{{{section_name}}}\n" + \
                     " \\begin{itemize}[leftmargin=0.15in, label={}]\n" + \
                     "    \\small{\\item{\n"
            
            if isinstance(section_data, dict):
                # Handle structured data like skills
                entries = []
                for category, items in section_data.items():
                    items_str = ", ".join(items)
                    entries.append(f"     \\textbf{{{category}}}{{: {items_str}}}")
                section += " \\\\\n".join(entries)
            elif isinstance(section_data, list):
                # Handle list of bullet points
                section += "     " + " \\\\\n     ".join(section_data)
            
            section += "\n    }}\n \\end{itemize}\n\n"
            sections.append(section)
            
        return "\n".join(sections)