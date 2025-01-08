from . import db

class EmailThread(db.Model):
    __tablename__ = 'threads'
    thread_id = db.Column(db.Integer, primary_key=True)
    thread_topic = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, default=db.func.now(
    ), onupdate=db.func.now()) 

class Email(db.Model):
    __tablename__ = 'emails'
    email_record_id = db.Column(db.Integer, primary_key=True)
    sender_email = db.Column(db.String(50), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    receiver_email = db.Column(db.String(100), nullable=False)
    receiver_name = db.Column(db.String(100), nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey(
        'threads.thread_id'), nullable=False)
    email_received_at = db.Column(db.TIMESTAMP, nullable=True)
    email_subject = db.Column(db.String(100), nullable=False)
    email_content = db.Column(db.Text, nullable=True)
    is_resolved = db.Column(db.Boolean, default=True)
    coverage_percentage = db.Column(db.Integer)
    coverage_description = db.Column(db.Text)
    email_thread = db.relationship(
        'EmailThread', backref=db.backref('emails', lazy=True))
    image_path = db.Column(db.Text)

class Summary(db.Model):
    __tablename__ = 'summaries'
    summary_id = db.Column(db.Integer, primary_key=True) 
    thread_id = db.Column(db.Integer, db.ForeignKey(
        'threads.thread_id'), nullable=False) 
    summary_content = db.Column(db.Text, nullable=False)
    summary_created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    summary_modified_at = db.Column(db.TIMESTAMP, default=db.func.now(
    ), onupdate=db.func.now()) 
    thread = db.relationship(
        'EmailThread', backref=db.backref('summaries', lazy=True))

class SentimentEnum(db.Enum):
    CRITICAL = 'Critical'
    NEEDS_ATTENTION = 'Needs attention'
    NEUTRAL = 'Neutral'
    POSITIVE = 'Positive'

class EmailThreadSentiment(db.Model):
    __tablename__ = 'email_thread_sentiment'
    sentiment_id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey(
        'threads.thread_id'), nullable=False, primary_key=True)
    sentiments = db.Column(db.Enum('Critical', 'Needs attention',
                           'Neutral', 'Positive', name='sentiment'), nullable=False)
    timestamp = db.Column(db.TIMESTAMP, default=db.func.now())
    thread = db.relationship(
        'EmailThread', backref=db.backref('sentiments', lazy=True))

    @classmethod
    def save_sentiment(cls, thread_id, sentiment_category):
        existing_record = cls.query.filter_by(thread_id=thread_id).first()
        if existing_record:
            existing_record.sentiments = sentiment_category 
            existing_record.timestamp = db.func.now() 
        else:
            new_sentiment = cls(
                thread_id=thread_id,
                sentiments=sentiment_category,
                timestamp=db.func.now()
            )
            db.session.add(new_sentiment)
        db.session.commit()

class SOPDocument(db.Model):
    __tablename__ = 'sop_document'
    doc_id = db.Column(db.Integer, primary_key=True)
    doc_content = db.Column(db.LargeBinary, nullable=False)
    doc_timestamp = db.Column(db.TIMESTAMP, default=db.func.now())

class Category(db.Model):
    __tablename__ = 'query_categories'
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False)
    sop_doc_id = db.Column(db.Integer, db.ForeignKey(
        'sop_document.doc_id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    updated_at = db.Column(
        db.TIMESTAMP, default=db.func.now(), onupdate=db.func.now())

class SOPGapCoverage(db.Model):
    __tablename__ = 'sop_gap_coverage'
    coverage_id = db.Column(db.Integer, primary_key=True)
    faq_id = db.Column(db.Integer, db.ForeignKey(
        'faqs.faq_id'), nullable=False)
    sop_doc_id = db.Column(db.Integer, db.ForeignKey(
        'sop_document.doc_id'), nullable=False)
    gap_type = db.Column(db.Enum('Fully Covered', 'Partially Covered', 'Inaccurately Covered',
                         'Ambiguously Covered', 'Not Covered', name='gap_category'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    updated_at = db.Column(
        db.TIMESTAMP, default=db.func.now(), onupdate=db.func.now())

class FAQS(db.Model):
    __tablename__ = 'faqs'
    faq_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    faq = db.Column(db.Text, nullable=False)
    freq = db.Column(db.Integer, nullable=False, default=0)
    coverage_percentage = db.Column(db.Integer)
    coverage_description = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    updated_at = db.Column(
        db.TIMESTAMP, default=db.func.now(), onupdate=db.func.now())
    __table_args__ = (
        db.CheckConstraint('freq >= 0', name='chk_positive'),
    )

class StagingFAQS(db.Model):
    __tablename__ = 'staging_faqs'
    staging_faq_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True)
    thread_id = db.Column(db.Integer, db.ForeignKey(
        'threads.thread_id'), nullable=False)
    faq = db.Column(db.Text, nullable=False)
    coverage_percentage = db.Column(db.Integer)
    coverage_description = db.Column(db.Text)
    processed_flag = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    updated_at = db.Column(
        db.TIMESTAMP, default=db.func.now(), onupdate=db.func.now())

class StagingSopGapCoverage(db.Model):
    __tablename__ = 'staging_sop_gap_coverage'
    staging_coverage_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True)
    thread_id = db.Column(db.Integer, db.ForeignKey(
        'threads.thread_id'), nullable=False)
    sop_doc_id = db.Column(db.Integer, db.ForeignKey(
        'sop_documents.doc_id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey(
        'query_categories.category_id'), nullable=False)
    gap_type = db.Column(db.Enum('Fully Covered', 'Partially Covered', 'Inaccurately Covered',
                         'Ambiguously Covered', 'Not Covered', name='gap_category'), nullable=False)
    processed_flag = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.now())
    updated_at = db.Column(
        db.TIMESTAMP, default=db.func.now(), onupdate=db.func.now())
