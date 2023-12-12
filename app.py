from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_uploads import UploadSet, configure_uploads, IMAGES, DOCUMENTS
from werkzeug.utils import secure_filename
import os
import mysql.connector
from io import BytesIO
from flask import Flask, render_template, request, send_file
from distutils.log import debug 
from fileinput import filename 
from flask import *  
from cryptography.fernet import Fernet
from datetime import datetime  # Add this import for handling timestamps
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this to a more secure key

# MySQL database connection
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="database"
)
cursor = mydb.cursor(dictionary=True)

# Generate a key for encryption (Keep this key secret and safe!)
key = Fernet.generate_key()
cipher_suite = Fernet(key)


# Function to validate user credentials
def validate_user(userID, password):
    query = "SELECT * FROM users WHERE User_ID = %s AND User_Password = %s"
    cursor.execute(query, (userID, password))
    user = cursor.fetchone()
    return user

def get_user_files(user_id):
    query = "SELECT File_Name, TIMESTAMP, Uploader_Name, File_ID FROM files WHERE Uploader_ID = %s"
    cursor.execute(query, (user_id,))
    files = cursor.fetchall()
    return files

# Function to check if the user is an admin
def is_admin(user_id):
    return user_id == 0

# Function to log user activity
def log_activity(user_id, activity_description):
    timestamp = datetime.now()
    query = "INSERT INTO activity_logs (User_ID, Activity_Description, TIMESTAMP) VALUES (%s, %s, %s)"
    cursor.execute(query, (user_id, activity_description, timestamp))
    mydb.commit()

def get_all_users():
    query = "SELECT User_ID, File_Directory FROM users WHERE User_ID != 0"  # Assuming the admin user has User_ID = 0
    cursor.execute(query)
    users = cursor.fetchall()
    return users

def get_user(file_id):
    query = "SELECT Uploader_ID, File_Path, Uploader_Name, File_Name FROM files WHERE file_id = %s"  # Assuming the admin user has User_ID = 0
    cursor.execute(query , (file_id,))
    user = cursor.fetchone()
    return user

def get_all_files():
    # Modify this function to fetch all files
    query = "SELECT File_Name, Uploader_Name, Uploader_ID, Time FROM files"
    cursor.execute(query)
    files = cursor.fetchall()
    return files

def get_file_name(file_id):
    query = "SELECT File_Name FROM files WHERE File_ID = %s"
    cursor.execute(query, (file_id,))
    result = cursor.fetchone()
    return result['File_Name'] if result else None

def get_file_directory(userID):
    query = "SELECT File_Directory from users WHERE User_ID = %s"
    cursor.execute(query, (userID,))
    result = cursor.fetchone()
    if result:
        return result['File_Directory']
    else:
        return None

def get_user_name(user_id):
    query = "SELECT User_Name FROM users WHERE User_ID = %s"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    return result['User_Name'] if result else "Unknown User"

def get_requests():
    query = "SELECT * FROM request"
    cursor.execute(query)
    requests = cursor.fetchall()
    return requests

# Function to save file information in the database
def save_file_info(file_name, uploader_id, file_directory, uploader_name):
    current_time = datetime.now()
    query = "INSERT INTO files (File_Name, Uploader_ID, Time, File_Path, Uploader_Name) VALUES (%s, %s, %s, %s, %s)"
    values = (file_name, uploader_id, current_time, file_directory, uploader_name)
    cursor.execute(query, values)
    mydb.commit()

# Function to encrypt a file
def encrypt_file(file_path):
    with open(file_path, 'rb') as file:
        file_data = file.read()
        encrypted_data = cipher_suite.encrypt(file_data)

    encrypted_file_path = file_path + '.encrypted'
    with open(encrypted_file_path, 'wb') as encrypted_file:
        encrypted_file.write(encrypted_data)

    return encrypted_file_path

# Function to decrypt a file
def decrypt_file(encrypted_file_path):
    with open(encrypted_file_path, 'rb') as encrypted_file:
        encrypted_data = encrypted_file.read()
        decrypted_data = cipher_suite.decrypt(encrypted_data)

    decrypted_file_path = encrypted_file_path.rsplit('.', 1)[0]  # Remove the '.encrypted' extension
    with open(decrypted_file_path, 'wb') as decrypted_file:
        decrypted_file.write(decrypted_data)

    return decrypted_file_path

@app.route('/')
def main_page():
    return render_template('main_page.html')

@app.route('/helpline', methods = ['GET', 'POST'])
def helpline():
    return render_template('helpline.html')

@app.route('/FileSystem', methods=['POST'])
def file_system():
    if request.method == 'POST':
        userID = request.form['User_ID']
        password = request.form['password']

        # Validate user credentials
        user = validate_user(userID, password)

        if user:
            # If the user is valid, store user_id in the session
            session['username'] = user['User_Name']
            session['user_id'] = user['User_ID']

            # Log user login activity
            log_activity(session['user_id'], 'User login')

            # Redirect to FileSystem.html
            return redirect(url_for('file_system'))
        else:
            # If the user is not valid, display an error message
            #flash('Invalid username or password. Please try again.', 'error')

            # Log failed login attempt
            log_activity(userID, 'Failed login attempt')

            return redirect(url_for('main_page'))

@app.route('/FileSystem')
def file_system_page():
    # Check if the user is logged in
    if 'user_id' in session:
        user_id = session['user_id']
        # We are doing this in two functions so that we can then mark the users not authenticated to see the files as not authorised
        if is_admin(user_id):
            # If the user is admin, fetch all files
            # Fetch user-specific files and pass them to the template
            files = get_all_files() 
        else:
            # If the user is not admin, fetch user-specific files
            #files = get_user_files(user_id)
            files = get_all_files()
        # Fetch and display requests
        requests = get_requests()
        return render_template('FileSystem.html', get_file_name=get_file_name, files=files, is_admin=is_admin, requests=requests)
    else:
        # If the user is not logged in, redirect to the login page
        #flash('Please log in to access the file system.', 'error')
        return redirect(url_for('main_page'))

@app.route('/upload', methods = ['GET', 'POST'])
def uploadfile():
   if request.method == 'POST':
        f = request.files['file']
        user_id = session['user_id']
        username = session['username']
        
        # Log file upload activity
        log_activity(user_id, f'File upload: {f.filename}')

        if is_admin(user_id):
            # Admin user: Get the main folder path
            admin_path = get_file_directory(user_id)

            # Get a list of all users (excluding the admin)
            all_users = get_all_users()  # You need to implement this function to fetch all users

            # Loop through each user and save the file in their subfolder
            for user in all_users:
                user_path = os.path.join(admin_path, user['File_Directory'])
                os.makedirs(user_path, exist_ok=True)
                file_path = os.path.join(user_path, secure_filename(f.filename))
                f.save(file_path)
                # Encrypt the uploaded file
                encrypted_file_path = encrypt_file(file_path)
                save_file_info(f.filename, user_id, file_path, username)
                os.remove(file_path)
        else:
            # Regular user: Save the file in their own subfolder
            user_path = get_file_directory(user_id)
            os.makedirs(user_path, exist_ok=True)
            file_path = os.path.join(user_path, secure_filename(f.filename))
            f.save(file_path)
            # Encrypt the uploaded file
            encrypted_file_path = encrypt_file(file_path)
            save_file_info(f.filename, user_id, file_path, username)
            os.remove(file_path)
        return render_template('uploadsuccess.html')

@app.route('/requests')
def requests_page():
    if 'user_id' in session :
        return render_template('request_page.html')
    return redirect(url_for('main_page'))

@app.route('/submit_request', methods=['POST'])
def submit_request():
    if 'user_id' in session:
        user_id = session['user_id']
        file_id = request.form['file_id']
        message = request.form['message']
        request_user = get_user(file_id)

        # Log request submission activity
        log_activity(user_id, f'Request submission: {message}')

        # Insert the request into the database
        query = "INSERT INTO request (User_ID, Request_User_ID, File_ID, Message, File_Path) VALUES (%s, %s, %s, %s, %s)"
        values = (user_id, request_user['Uploader_ID'], file_id, message, request_user['File_Path'])
        cursor.execute(query, values)
        mydb.commit()

        #flash('Request submitted successfully!', 'success')
        return redirect(url_for('file_system_page'))

    return redirect(url_for('main_page'))

# Function to approve the request in the database
def approve_request_in_database(request_id):
    # Update the request status to 'Approved' in the database
    update_query = "UPDATE request SET Status = 'Approved' WHERE Request_User_ID = %s"
    cursor.execute(update_query, (request_id,))
    mydb.commit()

# Add these routes to your existing app.py file

@app.route('/approve_request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    # Logic to approve the request in the database
    approve_request_in_database(request_id)

    # Log request approval activity
    log_activity(session['user_id'], f'Request approval: {request_id}')

    # Optionally, you can redirect to a success page or the main file system page
    return redirect(url_for('file_system_page'))

# Function to reject the request in the database
def reject_request_in_database(request_id):
    # Update the request status to 'Rejected' in the database
    update_query = "UPDATE request SET Status = 'Rejected' WHERE Request_User_ID = %s"
    cursor.execute(update_query, (request_id,))
    mydb.commit()

# Add these routes to your existing app.py file

@app.route('/reject_request/<int:request_id>', methods=['POST'])
def reject_request(request_id):
    # Logic to reject the request in the database
    reject_request_in_database(request_id)

    # Log request rejection activity
    log_activity(session['user_id'], f'Request rejection: {request_id}')

    # Optionally, you can redirect to a success page or the main file system page
    return redirect(url_for('file_system_page'))

@app.route('/activity_logs')
def activity_logs():
    # Fetch activity logs from the database
    query = "SELECT * FROM activity_logs"
    cursor.execute(query)
    activity_logs = cursor.fetchall()

    return render_template('Activitylogs.html', get_user_name=get_user_name, activity_logs=activity_logs)

if __name__ == '__main__':
    app.run(debug=True)