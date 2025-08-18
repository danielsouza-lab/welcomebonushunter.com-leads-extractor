"""Setup configuration for WordPress Leads Extractor."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="wordpress-leads-extractor",
    version="1.0.0",
    author="Rolling Riches",
    author_email="support@rollingriches.com",
    description="Extract and sync WordPress form leads to MySQL with data cleaning and validation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rolling-riches/wordpress-leads-extractor",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "wp-leads-extract=wordpress_leads_extractor.main:main",
            "wp-leads-sync=sync_to_mysql:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/rolling-riches/wordpress-leads-extractor/issues",
        "Source": "https://github.com/rolling-riches/wordpress-leads-extractor",
        "Documentation": "https://github.com/rolling-riches/wordpress-leads-extractor/wiki",
    },
)
