from flask import Blueprint, jsonify, request
from ..models import EmailThread, StagingFAQS, db, Summary, SOPGapCoverage, FAQS, Email
from ..utils import sortEmails, get_summary, get_pdf_content_by_doc_id, sop_email, BUSINESS_SIDE_NAME, BUSINESS_SIDE_EMAIL
from threading import Thread
from .. import create_app
from typing import Optional, Union, List, Dict
import base64
from PIL import Image
from io import BytesIO

app = Blueprint('ai', __name__)

def store_email_document_helper(thread_id: int, doc_id: int) -> Optional[Union[dict, None]]:
    try:
      app = create_app()
      with app.app_context():
        # Fetch all valid email thread based on thread_id
        email_thread = EmailThread.query.get(thread_id)
        if not email_thread:
            return jsonify({'error': "Email thread not found"}), 404

        document = get_pdf_content_by_doc_id(doc_id)

        if not document:
            return jsonify({'error': "Document not found"}), 404

        sorted_emails = sorted(
            email_thread.emails,
            key=lambda email: email.email_received_at or db.func.now(),
            reverse=True
        )
        latest_email = sorted_emails[0]

        discussion_thread = ""
        for email in sorted_emails:
            sender = email.sender_email
            date = email.email_received_at.strftime(
                '%B %d, %Y %I:%M %p') if email.email_received_at else None
            content = email.email_content
            email_entry = f"From: {sender}\nDate: {date}\nContent: {content}\n\n"
            discussion_thread += email_entry

        res = sop_email(email_thread.thread_topic, discussion_thread, latest_email.sender_name, document)
        if (not res):
            raise Exception("Something went wrong with LLM response")
        (content, coverage_percentage, coverage_description, faq) = res
        customerName, customerEmail = latest_email.sender_name, latest_email.sender_email
    
        new_staging_faq = StagingFAQS(
            thread_id = thread_id
         ,  faq = faq
         ,  coverage_description = coverage_description
         , coverage_percentage = coverage_percentage
            )
        
        new_email = Email(
            sender_email = BUSINESS_SIDE_EMAIL,
            sender_name = BUSINESS_SIDE_NAME,
            thread_id = thread_id,
            email_subject = email_thread.thread_topic,
            email_content = content,
            receiver_email = customerName,
            receiver_name = customerEmail,
            email_received_at = db.func.now(), 
            is_resolved = False,
            coverage_percentage = coverage_percentage,
            coverage_description = coverage_description
        )
        db.session.add(new_email)
        db.session.add(new_staging_faq)
        db.session.commit()
    except Exception as e:
        print ("Exception occurred during SOP based email response: ", e)
        return None

@app.route('/store_thread_and_document', methods=['POST'])
def store_email_document() -> tuple[dict, int]:
    data = request.json

    if not data:
        return {jsonify({'error:' 'cannot decode json data'})}, 400

    thread_id = data.get('thread_id')
    document_id = data.get('doc_id')

    if not thread_id or not document_id:
        return jsonify({'error': "Provide valid thread_id and documemnt_id"}), 400

    Thread(target=store_email_document_helper,
           args=(thread_id, document_id)).start()
    return jsonify({'success': 'Processing started in background', 'thread_id': thread_id}), 200

def encode_and_resize(image):
    W, H = image.size
    # image = image.resize((IMG_RES, int(IMG_RES * H / W)))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded_image

@app.post('/summarize/<int:thread_id>')
def summarize_thread_by_id(thread_id: int) -> Union[Summary, dict]:
    summaryOption = request.args.get('option')
    thread = EmailThread.query.get(thread_id)
    if not thread:
        return jsonify({'error': 'Thread not found'}), 404

    # True means sort in Asc order
    sorted_emails = sortEmails(thread.emails, True)
    discussion_thread = ""

    encoded_image = None

    for email in sorted_emails:
        if email.image_path:
            image = Image.open(email.image_path)
            encoded_image = encode_and_resize(image)

        sender = email.sender_email
        date = email.email_received_at.strftime(
            '%B %d, %Y %I:%M %p') if email.email_received_at else None
        content = email.email_content
        email_entry = f"From: {sender}\nDate: {date}\nContent: {content}\n\n"
        discussion_thread += email_entry

    response = get_summary(discussion_thread, summaryOption, encoded_image)
    thread_summary = Summary(
        thread_id=thread.thread_id,
        summary_content=response
    )
    db.session.add(thread_summary)
    db.session.commit()
    return (response)

@app.route('/get_category_gap/<int:doc_id>', methods=['GET'])
def get_category_gaps(doc_id: int) -> tuple[dict, list[dict]]:
    enum_counts = (
        db.session.query(
            SOPGapCoverage.gap_type,
            db.func.count(SOPGapCoverage.coverage_id).label('count')
        )
        .filter(SOPGapCoverage.sop_doc_id == doc_id)
        .group_by(SOPGapCoverage.gap_type)
        .all()
    )
    count_dict = {
        gap_type: 0 for gap_type in
        ['Fully Covered', 'Partially Covered', 'Inaccurately Covered',
            'Ambiguously Covered', 'Not Covered']
    }
    for gap_type, count in enum_counts:
        count_dict[gap_type] = count
    gaps = (
        db.session.query(
            FAQS.faq,
            SOPGapCoverage.gap_type,
            SOPGapCoverage.coverage_id
        )
        .join(SOPGapCoverage, FAQS.faq_id == SOPGapCoverage.faq_id)
        .filter(SOPGapCoverage.sop_doc_id == doc_id)
        # You can change the ordering here
        .order_by(SOPGapCoverage.coverage_id)
        .all()
    )
    gap_list = [
        {
            "faq": gap.faq,
            "gap_type": gap.gap_type,
            "id": gap.coverage_id
        }
        for gap in gaps
    ]
    response = {
        "count": count_dict,
        "gaps": gap_list
    }
    return jsonify(response)

@app.route('/staging_faq', methods=['GET'])
def get_stating_faq() -> List[Dict[str, Union[str, int]]]:
    stagingFaqs = StagingFAQS.query.all()
    stagingFaqList = []
    for stagingFaq in stagingFaqs:
        stagingFaqList.append(
                    {
                        "faq": stagingFaq.faq,
                        "coverage_percentage": stagingFaq.coverage_percentage
                        }
                )
    return jsonify(stagingFaqList)

@app.get('/get_faqs_with_freq')
def get_faqs_with_freq() -> List[Dict[str, Union[str, int]]]:
    faqs = FAQS.query.with_entities(
        FAQS.faq, FAQS.freq, FAQS.coverage_percentage, FAQS.coverage_description).order_by(FAQS.freq.desc()).all()
    print(faqs)
    faq_list = [{"faq": faq.faq, "freq": faq.freq, "coverage_percentage": faq.coverage_percentage, "coverageDescription": faq.coverage_description} for faq in faqs]
    return jsonify(faq_list)

autoSendEnable = False
thresholdVal = 101

@app.post('/set_auto_send/<isAutoSend>/<int:threshold>')
def setAutoSend(isAutoSend: str, threshold: int) -> tuple[dict, int]:
    global autoSendEnable
    global thresholdVal
    
    autoSendEnable = True if (isAutoSend == "true") else False
    thresholdVal = threshold
    return jsonify({}),200

@app.get('/get_auto_send')
def getAutoSend() -> jsonify:
    return jsonify({"isAutoSend": autoSendEnable, "thresholdVal": thresholdVal})
