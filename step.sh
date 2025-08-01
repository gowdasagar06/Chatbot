sudo yum install pip

pip install -r requirements.txt

python3 -m venv venv
source venv/bin/activate

streamlit run app.py

/home/ec2-user/chatbot/config/model_config.json