from flask import Blueprint, jsonify, request, send_file
from ..models import EmailThread, Email, db, EmailThreadSentiment, SOPDocument
from ..utils import getSentimentHelper, BUSINESS_SIDE_EMAIL, BUSINESS_SIDE_NAME, getCustomerNameAndEmail
from datetime import datetime, timezone
from typing import Union, Any, List, Dict
from werkzeug.exceptions import BadRequest, NotFound  # Import for raising exceptions
import os


app = Blueprint('main', __name__)

@app.route('/')
def hello() -> str:
    return "Hello, User!"

@app.route('/all_email_threads', methods=['GET'])
def get_all_threads() -> Dict[str, Union[List[Dict], str]]:
    threads = EmailThread.query.order_by(EmailThread.updated_at.desc(
    ), EmailThread.created_at.desc(), EmailThread.thread_id.desc()).all()

    thread_list = []
    for thread in threads:
        sentiment_record = EmailThreadSentiment.query.filter_by(
            thread_id=thread.thread_id).first()
        sentiment = getSentimentHelper(sentiment_record)

        sorted_emails = sorted(
            thread.emails,
            key=lambda email: email.email_received_at or db.func.now(),
            reverse=True
        )
        emails = [{
            'seq_no': i,
            'emailRecordId': email.email_record_id,
            'sender': email.sender_name,
            'senderEmail': email.sender_email,
            'receiver': email.receiver_name,
            'receiverEmail': email.receiver_email,
            'date': email.email_received_at.strftime('%B %d, %Y %I:%M %p') if email.email_received_at else None,
            'content': email.email_content,
            'isOpen': False,
            'isResolved': email.is_resolved,
            'coveragePercentage': email.coverage_percentage,
            'coverageDescription' : email.coverage_description,
            'imagePath': email.image_path
        } for i, email in enumerate(sorted_emails)]

        thread_list.append({
            'threadId': thread.thread_id,
            'threadTitle': thread.thread_topic,
            'emails': emails,
            'sentiment': sentiment
        })
    return jsonify({"threads": thread_list, "time": datetime.now(timezone.utc).strftime("%d-%m-%y_%H:%M:%S")})

ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg'}
MAX_IMAGE_SIZE = 500 * 1024  # 500KB
UPLOAD_FOLDER = "/home/user/Documents/github/email-summarizer-backend/uploads"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def spaces_to_underscore(txt: str) -> str:
    new_txt = ""
    for ch in txt:
        if ch == " ":
            new_txt += "_"
        else:
            new_txt += ch
    return new_txt


@app.route('/create/email', methods=['POST'])
def create_email() -> Union[dict, BadRequest]:
    if 'senderEmail' not in request.form or 'subject' not in request.form or 'content' not in request.form:
        return jsonify({'error': 'Missing required fields'}), 400

    sender_email = request.form['senderEmail']
    subject = request.form['subject']
    content = request.form['content']
    
    # Handle the image file
    image = request.files.get('image')
    image_path = None
    if image:
        if not allowed_file(image.filename):
            return jsonify({'error': 'Image type not allowed. Only PNG and JPEG are accepted.'}), 400
        if len(image.read()) > MAX_IMAGE_SIZE:
            return jsonify({'error': 'Image size exceeds the 500KB limit.'}), 400
        image.seek(0)  # Reset the file pointer to the start

        # Save the image or process it as needed
        image_path = os.path.join(UPLOAD_FOLDER, spaces_to_underscore(image.filename))
        image.save(image_path)

    # Assuming EmailThread and Email are defined models
    new_thread = EmailThread(thread_topic=subject)
    db.session.add(new_thread)
    db.session.flush()

    new_email = Email(
        sender_email=sender_email,
        sender_name=sender_email.split('@')[0],
        thread_id=new_thread.thread_id,
        email_subject=subject,
        email_content=content,
        receiver_email=BUSINESS_SIDE_EMAIL,
        receiver_name=BUSINESS_SIDE_NAME,
        email_received_at=db.func.now(),
        image_path = image_path
    )
    db.session.add(new_email)
    db.session.commit()

    return jsonify({'success': 'Email and thread created successfully', 
                    'thread_id': new_thread.thread_id, 
                    'email_record_id': new_email.email_record_id}), 201

@app.route('/create/email/<int:thread_id>', methods=['POST'])
def add_email_to_thread(thread_id: int) -> Union[dict, BadRequest, NotFound]:
    sender_email = request.form['senderEmail']
    subject = request.form['subject']
    content = request.form['content']
    
    # Handle the image file
    image = request.files.get('image')
    image_path = None
    if image:
        if not allowed_file(image.filename):
            return jsonify({'error': 'Image type not allowed. Only PNG and JPEG are accepted.'}), 400
        if len(image.read()) > MAX_IMAGE_SIZE:
            return jsonify({'error': 'Image size exceeds the 500KB limit.'}), 400
        image.seek(0)  # Reset the file pointer to the start

        # Save the image or process it as needed
        image_path = os.path.join(UPLOAD_FOLDER, spaces_to_underscore(image.filename))
        image.save(image_path)

    thread = EmailThread.query.get(thread_id)
    if not thread:
        return jsonify({'error': 'Thread not found'}), 404
    customerName, customerEmail = getCustomerNameAndEmail(thread.emails)

    new_email = Email(
        sender_email=sender_email,
        sender_name=sender_email.split('@')[0],
        thread_id = thread.thread_id,
        email_subject=subject,
        email_content=content,
        receiver_email=customerEmail,
        receiver_name=customerName,
        email_received_at=db.func.now(),
        image_path = image_path
    )
    db.session.add(new_email)
    db.session.commit()

    return jsonify({'success': 'Email and thread created successfully', 
                    'thread_id': thread.thread_id, 
                    'email_record_id': new_email.email_record_id}), 201

@app.route("/download_img/<int:email_id>", methods=["GET"])
def download_image(email_id: int):
    email_record = Email.query.get(email_id)
    if not email_record or not email_record.image_path:
        return jsonify({'error': 'Image not found for this email ID'}), 404
    image_path = email_record.image_path
    if not os.path.isfile(image_path):
        return jsonify({'error': 'Image file not found on server'}), 404
    try:
        return send_file(image_path, as_attachment=True, download_name="downloaded_image")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.post('/upload_sop_doc/')
def store_sop_doc_to_db() -> Union[dict, BadRequest]:
    if "file" not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files["file"]
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    binary_data = file.read()
    sop_document = SOPDocument(doc_content=binary_data)
    db.session.add(sop_document)
    db.session.commit()
    return jsonify({}), 200

@app.route("/check_new_emails/<last_updated_timestamp>", methods=["GET"])
def check_new_emails(last_updated_timestamp: str) -> List[Dict[str, Any]]:
    dt = datetime.strptime(last_updated_timestamp, "%d-%m-%y_%H:%M:%S")
    threads = EmailThread.query.all()
    for thread in threads:
        if thread.updated_at > dt:
            print("New mail found in the DB, fetching new emails: ",
                  thread.updated_at, dt)
            return get_all_threads()
    return jsonify([])


@app.route('/update/email/<int:email_id>', methods=['PUT'])
def update_email(email_id: int) -> tuple[dict, int]:
    data = request.json
    if not data or not data['content']:
        return jsonify({'error': 'Field not provided for update'}), 400

    email_record = Email.query.get(email_id)
    if not email_record:
        return jsonify({'error': 'Email not found'}), 404

    email_record.email_content = data['content']
    email_record.is_resolved = True

    db.session.commit()
    return jsonify({'success': 'Email updated successfully', 'email': {
        'email_record_id': email_record.email_record_id,
        'content': email_record.email_content
    }}), 200
