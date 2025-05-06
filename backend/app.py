from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
import os
import subprocess
import tempfile
from dotenv import load_dotenv
import traceback
import logging
import sys
import numpy as np
import shutil
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Configure CORS to allow requests from your frontend
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Create directories for storing files
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BACKEND_DIR, 'media')
VIDEOS_DIR = os.path.join(MEDIA_DIR, 'videos')

# Ensure directories exist
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

# Configure Gemini API
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

def find_manim_executable():
    """Find the Manim executable in the Python environment."""
    try:
        # Get the Python executable path
        python_path = sys.executable
        logger.info(f"Using Python executable: {python_path}")
        
        # Check if Python exists
        if not os.path.exists(python_path):
            raise Exception(f"Python executable not found at: {python_path}")
            
        # Try to find manim in the Python environment
        manim_path = os.path.join(os.path.dirname(python_path), 'Scripts', 'manim.exe')
        if os.path.exists(manim_path):
            logger.info(f"Found manim executable at: {manim_path}")
            return [manim_path]
            
        # If manim.exe not found, try using python -m manim
        logger.info("Manim executable not found, using python -m manim")
        return [python_path, '-m', 'manim']
        
    except Exception as e:
        logger.error(f"Error finding manim executable: {str(e)}")
        raise Exception(f"Could not find Manim executable: {str(e)}")

@app.route('/api/generate', methods=['POST', 'OPTIONS'])
def generate_animation():
    # Handle preflight request
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        logger.info("Received animation generation request")
        data = request.json
        if not data:
            logger.error("No JSON data received")
            return jsonify({'error': 'No data received'}), 400
            
        description = data.get('description')
        if not description:
            logger.error("No description provided")
            return jsonify({'error': 'Description is required'}), 400

        logger.info(f"Generating animation for description: {description}")

        # Create the animation
        output_file = create_animation(description)
        
        if not os.path.exists(output_file):
            logger.error(f"Video file not found at: {output_file}")
            raise Exception("Video file was not generated")
            
        logger.info(f"Video generated successfully at: {output_file}")
        
        # Get the filename for the response
        filename = os.path.basename(output_file)
        
        try:
            # Send the video file
            return send_file(
                output_file,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.error(f"Error sending file: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error in generate_animation: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

def create_animation(description):
    """Create an animation based on the user's description using Manim."""
    try:
        # Find manim executable
        manim_cmd = find_manim_executable()
        if not manim_cmd:
            raise Exception("Could not find Manim executable. Please make sure Manim is installed correctly.")
        
        logger.info(f"Using Manim command: {' '.join(manim_cmd)}")
        
        # Ask Gemini to generate Manim code
        prompt = f"""Create an elegant Manim animation for this description: "{description}"
        
        Requirements:
        1. Use these shapes and elements:
           - Basic shapes (Circle, Square, Rectangle, Line)
           - Transformations (FadeIn, FadeOut, Transform)
           - Smooth movements (MoveToTarget, Rotate)
        2. Create visually appealing compositions
        3. Keep the animation upto 10 seconds
        4. Use proper spacing and positioning
        5. Create objects one at a time with smooth transitions
        
        Example code structure:
        from manim import *
        
        class ElegantScene(Scene):
            def construct(self):
                # Create main elements
                circle = Circle(radius=0.5, color=BLUE)
                self.play(FadeIn(circle))
                
                # Add complementary elements
                square = Square(side_length=1, color=RED)
                square.next_to(circle, RIGHT, buff=0.5)
                self.play(FadeIn(square))
                
                # Create smooth movement
                self.play(
                    circle.animate.move_to([-2, 0, 0]),
                    square.animate.move_to([2, 0, 0]),
                    run_time=2
                )
                
                # Add final touch
                self.play(
                    Rotate(circle, angle=PI),
                    Rotate(square, angle=-PI),
                    run_time=1.5
                )
                self.wait(1)
        
        Return ONLY the Python code, no explanations."""

        try:
            response = model.generate_content(prompt)
            scene_code = response.text.strip()
            logger.info(f"Generated code from Gemini: {scene_code}")
            
            # Clean up the code
            scene_code = scene_code.replace('```python', '').replace('```', '').strip()
            
            # Create a temporary file for the scene
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(scene_code)
                temp_file_path = f.name
            
            logger.info(f"Created temporary file at: {temp_file_path}")
            
            # Get the scene class name
            scene_class_name = None
            for line in scene_code.split('\n'):
                if 'class' in line and '(Scene)' in line:
                    scene_class_name = line.split('class')[1].split('(')[0].strip()
                    break
            
            if not scene_class_name:
                raise ValueError("Could not find Scene class in generated code")
            
            logger.info(f"Found scene class name: {scene_class_name}")
            
            # Generate unique output filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'animation_{timestamp}.mp4'
            
            # Prepare Manim command
            cmd = manim_cmd + [
                '-qh',  # High quality
                '--media_dir', MEDIA_DIR,  # Explicit output directory
                '-o', output_filename,  # Output file name
                temp_file_path,  # Input file
                scene_class_name  # Scene class name
            ]
            
            logger.info(f"Running Manim command: {' '.join(cmd)}")
            
            # Run the command with a timeout
            try:
                # Ensure the media directory exists
                os.makedirs(MEDIA_DIR, exist_ok=True)
                
                result = subprocess.run(
                    cmd,
                    cwd=MEDIA_DIR,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"Manim error: {result.stderr}")
                    logger.error(f"Manim stdout: {result.stdout}")
                    raise Exception(f"Manim failed: {result.stderr}")
                
                logger.info(f"Manim output: {result.stdout}")
                
            except subprocess.TimeoutExpired:
                logger.error("Manim command timed out after 5 minutes")
                raise Exception("Animation generation timed out")
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            # Find the generated video file
            temp_dir = os.path.basename(temp_file_path).replace('.py', '')
            video_dir = os.path.join(MEDIA_DIR, 'videos', temp_dir, '1080p60')
            
            if not os.path.exists(video_dir):
                logger.error(f"Video directory not found: {video_dir}")
                raise Exception("Video directory was not created")
                
            # Look for the video file in the directory
            video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
            if not video_files:
                logger.error(f"No video files found in {video_dir}")
                raise Exception("No video files were generated")
                
            # Get the most recent video file
            output_file = os.path.join(video_dir, video_files[-1])
            logger.info(f"Found video file: {output_file}")
            
            # Copy the video file to the videos directory for easier access
            final_output_file = os.path.join(VIDEOS_DIR, output_filename)
            shutil.copy2(output_file, final_output_file)
            logger.info(f"Copied video file to: {final_output_file}")
            
            return final_output_file
            
        except Exception as e:
            logger.error(f"Error in create_animation: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    except Exception as e:
        logger.error(f"Error in create_animation: {str(e)}")
        logger.error(traceback.format_exc())
        raise

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0') 