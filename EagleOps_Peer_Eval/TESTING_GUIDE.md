# EagleOps Peer Evaluation Testing Guide

This guide will help you test the course management and form features in the EagleOps Peer Evaluation system.

## Setup

1. Make sure the database migrations have been applied:
   ```
   python manage.py migrate
   ```

2. Run the demo data creation script:
   ```
   python manage.py shell < create_demo_data.py
   ```

3. Start the development server:
   ```
   python manage.py runserver
   ```

4. Visit http://127.0.0.1:8000/ in your browser

## Testing Course Management

### Viewing Courses

1. Log in to the application
2. Navigate to the Courses page from the navigation menu
3. You should see the "Demo Course" that was created by the demo script
4. If logged in as an admin, you should also see a "Create New Course" button

### Creating a New Course

1. Click the "Create New Course" button (admin only)
2. Fill out the form with:
   - Course Name: "Introduction to Computer Science"
   - Course Code: "CS101"
   - Description: "A first course in computer science covering programming fundamentals"
3. Click "Create Course"
4. You should be redirected to the course detail page for your new course

### Viewing Course Details

1. From the Courses page, click on a course card
2. The course detail page should show:
   - The course name and code
   - Sections for Form Templates and Forms (initially empty)
   - Team information
3. If you're an admin or instructor, you should see options to create templates and forms

## Testing Form Templates

### Creating a Form Template

1. From a course detail page, click "Create Template"
2. Fill out the form with:
   - Title: "Peer Assessment Template"
   - Description: "Template for evaluating team member contributions"
3. Add questions:
   - Click "Add Question"
   - Enter question text: "How effectively did this team member communicate?"
   - Question type: "Likert Scale (1-5)"
   - Add more questions as desired
4. Click "Save Template"
5. You should be redirected back to the course detail page with your new template listed

### Editing a Template

1. From the course detail page, find your template and click "Edit"
2. Modify the title, description, or questions
3. Click "Save Template"
4. Verify your changes were saved

### Duplicating a Template

1. From the course detail page, find a template and click "Duplicate"
2. A new template with "(Copy)" in the title should appear in the list

## Testing Forms

### Creating a Form

1. From the course detail page, click "Create Form"
2. Fill out the form with:
   - Title: "Midterm Peer Evaluation"
   - Select a template
   - Set publication and closing dates
   - Select teams to assign the form to
   - Choose whether to enable self-assessment
3. Click "Create Form"
4. The form should appear in the Forms list on the course detail page

### Publishing a Form

1. From the course detail page, find a form in "Draft" status
2. Click "Publish"
3. The form status should change to "Scheduled" or "Active" depending on the dates

## Profile Management

1. Click on your profile link in the navigation
2. Update your first and last name
3. View your team and course information
4. Click "Update Profile" to save changes

## Notes

- Administrators can see all courses and have full management capabilities
- Instructors can manage their assigned courses, templates, and forms
- Regular users can only view courses they are enrolled in through their team memberships

If you encounter any issues during testing, please check the server logs for error messages. 