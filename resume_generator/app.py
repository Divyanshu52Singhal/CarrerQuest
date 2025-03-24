from flask import Flask, request, send_file, render_template, redirect, url_for, jsonify
from flask_cors import CORS

from resume_generator import ResumeGenerator
from io import BytesIO

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def index():
    """Redirect to the resume form page."""
    return redirect(url_for('resume_form'))

@app.route('/form')
def resume_form():
    """Display the resume form page."""
    return render_template('resume_form.html')

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

@app.route('/preview', methods=['POST'])
def preview_resume():
    """
    Endpoint to receive form data and return the preview of generated resume.
    This doesn't download the file but returns the content for preview.
    """
    if not request.is_json:
        return {"error": "Content-Type must be application/json"}, 400
    
    data = request.get_json()
    
    # Generate LaTeX content
    latex_content = ResumeGenerator.from_json(data, "./resume_template.tex")
    
    # Return the content for preview
    return jsonify({"content": latex_content})

if __name__ == '__main__':
    app.run(debug=True)