import schedule
from datetime import datetime
import time
import ollama
import re
import json
from db_session import session
from models import EmailThread, StagingFAQS
from utils import get_str_between_braces
from typing import List, Tuple

def sortEmails(emailList: List[Tuple[str, str, str, str, datetime, str, str, bool, int, str]]) -> List[Tuple[str, str, str, str, datetime, str, str, bool, int, str]]:
    return sorted(emailList, key=lambda email: email.email_received_at)

def getDiscussionThread(thread: EmailThread) -> str:
    sorted_emails = sortEmails(thread.emails)
    discussion_thread = ""
    for email in sorted_emails:
        sender = email.sender_email
        date = email.email_received_at.strftime(
            '%B %d, %Y %I:%M %p') if email.email_received_at else None
        content = email.email_content
        email_entry = f"From: {sender}\nDate: {date}\nContent: {content}\n\n"
        discussion_thread += email_entry
    return discussion_thread

def update_staging_faq(thread: EmailThread) -> None:
    discussion_thread = getDiscussionThread(thread)
    json_format = """
        {\"sop_based_email_response\": \"<email response>\" ,
         \"sop_coverage_percentage\": \"<percentage>%\", 
         \"description_for_coverage_percentage\": \"<description>\" , 
        \"FAQ_based_on_email\":\"<A_generalized_FAQ_question_thread_summarizes_email_discussion>\"
         }
        """
    prompt = f"""
      You are a helpful assistant that generates responses based on company SOP guidelines. For the given email discussion:
    - generate a formal and professional response to this email, addressing each point appropriately.
    - Refer yourself as ABC support at the end of the mail.
    - Make sure to refer to the appropriate procedures mentioned in the subject and provide a comprehensive response,
    - including step-by-step guidelines, documentation, and any relevant timelines. Don't include the subject line in mail.
    - Do not mention subject in the response! Do not mention Image not found.
    - Also generate a percentage for how sufficient is the SOP document to generate an answer. Where 0% = topic not covered at all, 100% = topic is fully covered. 
    - Your output should be a JSON object that matches the following schema:
        {json_format}
    - Make sure it is a valid JSON object.
    - Use \n instead of whitespace or newline.
    - Never return anything other than a JSON object.

    Below are the emails asking about a specific process related to the company SOP.
    Email exchanges: 
    {discussion_thread}

    """
    res = ollama.generate(model='llama3.2', prompt=prompt)
    print(res['response'])
    jsonRes = get_str_between_braces(res['response'])
    if (not jsonRes):
        return
    try:
        encodedJson = json.loads(jsonRes)
    except Exception as e:
        print("failed while decoding: ", e)
        return
    if not all(k in encodedJson for k in ("sop_coverage_percentage", "FAQ_based_on_email", "description_for_coverage_percentage")):
        return
    percentage = int(
        encodedJson['sop_coverage_percentage'].replace('%', '').strip())
    stageFaq = StagingFAQS(
        thread_id=thread.thread_id, faq=encodedJson['FAQ_based_on_email'], coverage_percentage=percentage, coverage_description=encodedJson['description_for_coverage_percentage']
    )
    session.add(stageFaq)
    session.commit()

def run_faq_analysis() -> None:
    threads = session.query(EmailThread).all()
    for thread in threads:
        update_staging_faq(thread)  # Update sentiment for each thread

def job() -> None:
    print(f"Running sentiment analysis at {datetime.now()}")
    run_faq_analysis()

if __name__ == '__main__':
    schedule.every(5).hours.do(job)
    job()
    while True:
        schedule.run_pending()
        time.sleep(60)
