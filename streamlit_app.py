import streamlit as st
import openai
import time
import json
import re
import pandas as pd

# Set page config
st.set_page_config(page_title="Corn & Coke Recommendation", layout="wide")

api_key = st.secrets["api_key"]
client = openai.OpenAI(api_key=api_key)

data = pd.read_csv("database.csv")
data = data.dropna(subset="link_texts_0")
data["CSFD_YEAR"] = data["CSFD_YEAR"].astype(int)
data["rating"] = data["rating"].astype(int)

# Assuming 'data' is your dataframe
link_columns = [col for col in data.columns if col.startswith('link_texts_')]

# Stack the values from all link_texts_* columns into one column
combined_values = data[link_columns].stack().reset_index(drop=True)

# Count the occurrences of each unique value
value_counts = combined_values.value_counts().reset_index()

# Rename the columns for clarity
value_counts.columns = ['tag', 'count']

def startAssistantThread(prompt):
    messages = [{"role": "user", "content": prompt}]
    thread = client.beta.threads.create(messages=messages)
    return thread.id

def runAssistant(thread_id, assistant_id):
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
    return run.id

def checkRunStatus(thread_id, run_id):
    run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    return run.status

def retrieveThread(thread_id):
    thread_messages = client.beta.threads.messages.list(thread_id)
    list_messages = thread_messages.data
    thread_messages = []
    for message in list_messages:
        obj = {}
        obj['content'] = message.content[0].text.value
        obj['role'] = message.role
        thread_messages.append(obj)
    return thread_messages[::-1]

def count_matches(row, search_strings):
    count = 0
    for col in row.index:
        if col.startswith('link_texts_'):  # Ensuring only columns named link_texts_ are considered
            count += sum(1 for s in search_strings if s == str(row[col]))
    return count

st.image("baner.png") 

# Title of the app
st.title("Corn & Coke")
st.write("Movies recommender based on your prompts")

# Creating the form
with st.form("my_form"):
    text_input = st.text_input("Describe your mood or hastags:")
    submitted = st.form_submit_button("Submit")

    # Displaying output upon form submission
    if submitted:
        assistant_id = st.secrets["assistant_id"]
        prompt = text_input
        thread_id = startAssistantThread(prompt)
        run_id = runAssistant(thread_id, assistant_id)
        status = checkRunStatus(thread_id, run_id)
        while status == "in_progress" or status == "queued":
            time.sleep(1)
            status = checkRunStatus(thread_id, run_id)

        messages = retrieveThread(thread_id)
        message = messages[-1]
        content = message['content']
        content_dict = json.loads(content)
        tags = content_dict["tags"].split(",")
        tags = [tag.strip() for tag in tags]
        data['match_count'] = data.apply(count_matches, axis=1, search_strings=tags)
        data_result = data[["ORIGINAL_TITLE", "rating", "CSFD_YEAR", "match_count"]]
        if "lowest_year" in content_dict:
            data_result = data_result[data_result["CSFD_YEAR"] > int(content_dict["lowest_year"])]
        data_result = data_result.rename(columns={
            "ORIGINAL_TITLE": "Movie Title",
            "rating": "Rating",
            "CSFD_YEAR": "Release Year"
        })
        st.write(data_result.sort_values(["match_count", "Rating"], ascending=False).rename(columns={"ORIGINAL_TITLE_1": "Corn & Coke Recommendation"})[["Movie Title", "Rating", "Release Year"]].head().to_html(index=False).replace("<th>", "<th style='text-align: center'>").replace("<td>", "<td style='text-align: center'>"), unsafe_allow_html=True)
