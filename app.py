import streamlit as st
from chatbot.data_loader import load_conditions
from chatbot.symptom_extractor import extract_symptoms
from chatbot.diagnosis import format_diagnosis, evaluate_confirmed_conditions, save_log
import random

conditions = load_conditions()
st.set_page_config(page_title="🧠 Medical Assistant", layout="centered")
st.title("🩺 Medical Assistant")

# Step 1: Handle user info first
if "chat_started" not in st.session_state:
    st.session_state.chat_started = False
    st.session_state.user_data = {"name": "", "age": 0, "gender": ""}

if not st.session_state.chat_started:
    with st.form("user_info_form"):
        st.session_state.user_data["name"] = st.text_input("Enter your name:")
        st.session_state.user_data["age"] = st.number_input("Enter your age:", min_value=1, max_value=120, step=1)
        st.session_state.user_data["gender"] = st.selectbox("Select your gender:", ["Male", "Female", "Other"])
        submitted = st.form_submit_button("Start Chat")

    if submitted:
        if st.session_state.user_data["name"] and st.session_state.user_data["age"] and st.session_state.user_data["gender"]:
            st.session_state.chat_started = True
            st.rerun()
        else:
            st.warning("⚠️ Please fill in all fields to proceed.")

# Step 2: Start chat logic
if st.session_state.chat_started:
    # Initialize session states
    if "qa_log" not in st.session_state:
        st.session_state.qa_log = []
    if "chat" not in st.session_state:
        st.session_state.chat = []
        st.session_state.phase = "symptom_input"
        st.session_state.questions = []
        st.session_state.condition_map = {}
        st.session_state.conditions = []
        st.session_state.confirmed = {}
        st.session_state.negatives = {}
        st.session_state.follow_up = 0

    # Display chat history
    for entry in st.session_state.chat:
        with st.chat_message(entry["role"]):
            st.markdown(entry["message"])

    user_input = st.chat_input("Describe your symptoms...", key="symptom_input")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.chat.append({"role": "user", "message": user_input})

        # Phase 1: Symptom input
        if st.session_state.phase == "symptom_input":
            symptoms = extract_symptoms(user_input)
            if not symptoms:
                reply = "😕 I couldn't understand your symptoms. Please try again."
            else:
                st.session_state.symptoms = symptoms

                # First try to find conditions with ALL symptoms
                all_match = []
                for cond in conditions:
                    cond_syms = [s.lower() for s in cond.get("symptoms", [])]
                    if all(sym in cond_syms for sym in symptoms):
                        all_match.append(cond)

                # Fallback to ANY symptom match
                matches = all_match
                if not all_match:
                    any_match = []
                    for cond in conditions:
                        cond_syms = [s.lower() for s in cond.get("symptoms", [])]
                        if any(sym in cond_syms for sym in symptoms):
                            any_match.append(cond)
                    matches = any_match

                if not matches:
                    reply = "😕 No relevant conditions found for your symptoms."
                else:
                    # Get questions from matches
                    question_set = []
                    condition_map = {}
                    for cond in matches:
                        for q in cond.get("questions", []):
                            if q not in question_set:
                                question_set.append(q)
                                condition_map[q] = cond["name"]

                    if not question_set:
                        reply = "😕 No questions found for matched conditions."
                    else:
                        random.shuffle(question_set)
                        st.session_state.questions = question_set
                        st.session_state.condition_map = condition_map
                        st.session_state.conditions = matches
                        st.session_state.phase = "followup"
                        st.session_state.follow_up = 0
                        st.session_state.confirmed = {}
                        st.session_state.negatives = {}
                        reply = f"🤔 {question_set[0]} (yes/no)"

            st.chat_message("assistant").markdown(reply)
            st.session_state.chat.append({"role": "assistant", "message": reply})

        # Phase 2: Follow-up Q&A
        elif st.session_state.phase == "followup":
            answer = user_input.strip().lower()
            if answer not in ["yes", "no"]:
                msg = "❗ Please answer with 'yes' or 'no'."
                st.chat_message("assistant").markdown(msg)
                st.session_state.chat.append({"role": "assistant", "message": msg})
            else:
                current_question = st.session_state.questions[st.session_state.follow_up]
                condition_name = st.session_state.condition_map.get(current_question, "")

                st.session_state.qa_log.append({
                    "question": current_question,
                    "answer": answer
                })

                if answer == "yes":
                    st.session_state.confirmed[condition_name] = st.session_state.confirmed.get(condition_name, 0) + 1
                else:
                    st.session_state.negatives[condition_name] = st.session_state.negatives.get(condition_name, 0) + 1

                # End early if confirmed
                if st.session_state.confirmed.get(condition_name, 0) >= 3:
                    condition = next((c for c in st.session_state.conditions if c["name"] == condition_name), None)
                    if condition:
                        diagnosis = format_diagnosis(condition)
                        st.chat_message("assistant").markdown(diagnosis)
                        st.session_state.chat.append({"role": "assistant", "message": diagnosis})
                        st.session_state.phase = "done"
                        save_log(diagnosis)
                        st.stop()

                # Skip next questions if already 2 NOs
                while True:
                    st.session_state.follow_up += 1
                    if st.session_state.follow_up >= len(st.session_state.questions):
                        break
                    next_q = st.session_state.questions[st.session_state.follow_up]
                    next_cond = st.session_state.condition_map.get(next_q, "")
                    if st.session_state.negatives.get(next_cond, 0) < 2:
                        break

                if st.session_state.follow_up < len(st.session_state.questions):
                    next_q = st.session_state.questions[st.session_state.follow_up]
                    bot_msg = f"🤔 {next_q} (yes/no)"
                else:
                    # End of Q&A
                    diagnosis_text = evaluate_confirmed_conditions(
                        st.session_state.confirmed, st.session_state.conditions
                    )
                    st.chat_message("assistant").markdown(diagnosis_text)
                    st.session_state.chat.append({"role": "assistant", "message": diagnosis_text})
                    st.session_state.phase = "done"
                    save_log(diagnosis_text)
                    st.stop()

                st.chat_message("assistant").markdown(bot_msg)
                st.session_state.chat.append({"role": "assistant", "message": bot_msg})
