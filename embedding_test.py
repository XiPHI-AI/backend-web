import re

# Read the markdown file
input_file = "/home/samshetty/Downloads/exhaustive-job-roles-2025.md"
output_file = "jobroles_only.txt"

with open(input_file, 'r') as file:
    lines = file.readlines()

# Initialize a list to store skills
skills = []

# Process each line
for line in lines:
    # Skip headers (lines starting with ### or #)
    if line.strip().startswith('#'):
        continue
    # Skip empty lines or lines with only dashes
    if line.strip() == '' or line.strip().startswith('-'):
        continue
    # Skip the generated date and total count lines
    if line.strip().startswith('*Generated:') or line.strip().startswith('*Total Count:'):
        continue
    # Extract skills (assuming they are comma-separated in the lists)
    if ',' in line:
        # Split the line by commas and clean up each skill
        line_skills = [skill.strip() for skill in line.split(',')]
        skills.extend(line_skills)

# Write the skills to a new file
with open(output_file, 'w') as file:
    for skill in skills:
        file.write(skill + '\n')

print(f"Skills have been extracted to {output_file}")