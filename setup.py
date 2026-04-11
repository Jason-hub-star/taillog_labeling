"""Setup configuration"""

from setuptools import setup, find_packages

setup(
    name="taillog_labeling",
    version="0.1.0",
    description="YouTube dog behavior labeling pipeline",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "yt-dlp>=2023.12.0",
        "opencv-python>=4.8.0",
        "ultralytics>=8.0.0",
        "ollama>=0.1.0",
        "supabase>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "ruff>=0.1.0",
        ]
    },
)
