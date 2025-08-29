from email_reply_parser import EmailReplyParser

text = """Hello Alex,

Ez a levél tartalma.

--
Aláírás
"""

# Ez a legegyszerűbb: egy stringet ad vissza a "válasz szövegrészről"
body = EmailReplyParser.parse_reply(text)
print("Tiszta üzenet:")
print(body)
