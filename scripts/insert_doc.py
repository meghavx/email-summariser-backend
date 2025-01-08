import psycopg2
import binascii
from typing import List

# Path to the binary content file
pdf_file_path = "./uploads/SOP.pdf"

with open(pdf_file_path, "rb") as fp:
    binary_content = fp.read()

# Convert to PostgreSQL compatible hexadecimal format
hex_content = binascii.hexlify(binary_content).decode()

# Generate the SQL insert command
sql_insert = f"INSERT INTO sop_document (doc_content) VALUES (E'\\\\x{hex_content}');"

try:
    # Connect to PostgreSQL
    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        database="poc",
        user="ruchita",
        password="qwerty"
    )
    
    # Create a new database session and return a new cursor
    cursor = connection.cursor()

    # Execute the SQL command
    cursor.execute(sql_insert)
    
    # Commit the transaction
    connection.commit()

    print("Binary content inserted successfully.")

except Exception as error:
    print(f"Error occurred: {error}")

finally:
    # Close cursor and connection
    if cursor:
        cursor.close()
    if connection:
        connection.close()
