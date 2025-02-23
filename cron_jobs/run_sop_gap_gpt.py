import schedule
from datetime import datetime
import time
import json
from PyPDF2 import PdfReader
import io
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
import os
from dotenv import load_dotenv
from db_session import session
from models import SOPDocument, SOPGapCoverage , FAQS
from utils import text_splitter, get_str_between_braces
from typing import Optional

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

embeddings = OpenAIEmbeddings()
llm = ChatOpenAI(model="gpt-4", temperature=0.5, max_tokens=1000)

def get_pdf_content_by_doc_id(doc_id: int) -> Optional[str]:
    try:
        sop_document = session.query(SOPDocument).filter_by(doc_id=doc_id).one()
        if sop_document == None:
            return ""
        pdf_file = io.BytesIO(sop_document.doc_content)
        reader = PdfReader(pdf_file)
        pdf_content = " ".join([page.extract_text() for page in reader.pages])
        return pdf_content
    except Exception as e:
        print ("exception occurred",e)
        return None

def analyze_coverage_for_FAQ(mainFaq: FAQS, doc_content) -> Optional[SOPGapCoverage]:
    text_chunks = text_splitter.split_text(doc_content)
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vector_store.as_retriever(search_kwargs={"k": 3})  # Increased k for broader search
    )
    jsonFormat = "{ coverage_type: \"Coverage Type\", \"reason\": \"Reason for the coverage percentage\" }"

    prompt = f"""
    You are an assistant checking SOP compliance.
    Please evaluate how much of the following question is covered by the SOP and provide a detailed reason for your assessment.
    Inquiry: "{mainFaq.faq}"
    
    Your answer must include a coverage type (Fully Covered, Partially Covered, Ambiguously Covered, 
                                              Not Covered) followed by a detailed explanation of why you assigned this score.
    For example:
    - If it's Fully Covered, explain why.
    - If it's Partially Covered, mention what's missing.
    - If it's Ambiguously Covered, explain the gaps.
    - If it's Not Covered, mention why the question is out of context.
        Give me the response in json in this format: {jsonFormat} and nothing else.
    """
    answer = qa.run(prompt)
    print ("answer",answer)
    jsonRes = get_str_between_braces(answer)
    encodedJson = json.loads(jsonRes)
    print ("encodedJson",encodedJson)
    if (not jsonRes):
        return
    coverageType = encodedJson['coverage_type']
    if (not coverageType):
        print ("coverage type is wrong", coverageType)
        return
    sopGapCoverage = SOPGapCoverage(
                faq_id = mainFaq.faq_id
              , sop_doc_id = 1 # Always 1 by default
              , gap_type = coverageType
            )
    session.add(sopGapCoverage)
    session.commit()  
    

def run_gap_coverage_analysis() -> None:
    mainFaqs = session.query(FAQS).all()
    doc_content = get_pdf_content_by_doc_id(1)
    for mainFaq in mainFaqs:
        analyze_coverage_for_FAQ(mainFaq, doc_content)  # Passing doc_id = 1 by default

def job() -> None:
    print(f"Running gap coverage analysis by gpt at {datetime.now()}")
    run_gap_coverage_analysis()

if __name__ == '__main__':
    schedule.every(5).hours.do(job)
    job()
    while True:
        schedule.run_pending()
        time.sleep(60)
