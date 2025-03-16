from flask import Flask, request, send_file
from flask_cors import CORS  # Add this import

from resume_generator import ResumeGenerator
from io import BytesIO

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes 

@app.route('/generate', methods=['POST'])
def generate_resume():
    if not request.is_json:
        return {"error": "Content-Type must be application/json"}, 400
    
    data = request.get_json()
    
    # Generate LaTeX content
    latex_content = ResumeGenerator.from_json(data, "./resume_template.tex")
    
    # Create in-memory file
    mem_file = BytesIO(latex_content.encode('utf-8'))
    
    # Return the file
    return send_file(mem_file,
                    mimetype='application/x-tex',
                    as_attachment=True,
                    download_name='resume.tex')

if __name__ == '__main__':
    app.run(debug=True)