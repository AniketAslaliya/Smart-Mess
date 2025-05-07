import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- MongoDB Connection ---
client = MongoClient("mongodb+srv://mess:123@smartmess.o14pepz.mongodb.net/?retryWrites=true&w=majority&appName=SmartMess")
db = client["iot_test"]
collection = db["output"]  # Updated to new schema
alerts_collection = db["alerts"]
feedback_collection = db["feedback"]

# --- Utility Function ---
def load_data():
    data = list(collection.find())
    if not data:
        st.warning("No data found in MongoDB collection.")
        st.stop()
    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.day_name()
    return df

# --- Auto Notification Trigger ---
def check_and_trigger_refill_alert(latest_tray_weight):
    if latest_tray_weight < 300:
        recent_alert = alerts_collection.find_one(sort=[("timestamp", -1)])
        if not recent_alert or (datetime.utcnow() - recent_alert["timestamp"]).seconds > 1800:
            alerts_collection.insert_one({
                "message": "Tray level is low. Please refill the food tray immediately.",
                "timestamp": datetime.utcnow()
            })

# --- Manual Refresh Button ---
st.set_page_config(page_title="Smart Mess Dashboard", layout="wide")
st.title("🍽️ Smart Mess System Dashboard")
if st.sidebar.button("🔄 Refresh Dashboard"):
    st.experimental_set_query_params(refresh="true")
    st.rerun()

# --- Load Data ---
df = load_data()
role = st.sidebar.radio("👤 Select User Role", ["Student", "Mess Worker", "Mess Admin"])

# --- Trigger refill alert if needed ---
latest_row = df.sort_values("timestamp", ascending=False).iloc[0]
latest_tray = latest_row["tray_g"]
latest_waste = latest_row["waste_g"]
latest_seat = latest_row["seat_occupied"]
check_and_trigger_refill_alert(latest_tray)

# --- Reusable Status ---
def show_current_status():
    with st.container():
        st.subheader("📦 Current System Status")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tray Status", "LOW" if latest_tray < 300 else "MEDIUM" if latest_tray < 700 else "FULL", delta=f"{latest_tray:.1f} g")
        with col2:
            st.metric("Seat Occupancy", "✅ Occupied" if latest_seat else "Vacant")
        with col3:
            st.metric("Waste Level (g)", f"{latest_waste:.1f}")

# --- Student View ---
if role == "Student":
    st.header("📱 Student View")
    show_current_status()

    st.subheader("📊 Tray Level Over Time")
    fig = px.area(df, x="timestamp", y="tray_g", title="Tray Usage Trend (g)", color_discrete_sequence=["#2E91E5"])
    fig.update_traces(line_shape="spline")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🚦 Current Mess Status")
    if latest_tray < 300:
        st.error("🔴 Tray Low — Avoid visiting now")
    elif latest_tray < 700:
        st.warning("🟠 Tray Medium — Visit Soon")
    else:
        st.success("🟢 Tray Full — Visit Now")

    st.subheader("🪑 Seat Occupancy Info")
    st.metric("Seat Occupied", "✅" if latest_seat else "Vacant")

    st.subheader("📈 Peak Crowd Hours")
    seat_df = df[df["seat_occupied"] == True]
    peak_hour = seat_df["hour"].value_counts().idxmax() if not seat_df.empty else "N/A"
    st.info(f"🕓 Most crowded around: {peak_hour}:00 hrs" if peak_hour != "N/A" else "No seat occupancy data available.")

    # Day-based insight for students
    day_today = datetime.now().strftime("%A")
    st.info(f"Today is {day_today}. Based on trends, this day usually sees higher mess crowd or food popularity.")

    st.subheader("📢 Messages from Mess Admin")
    admin_msgs = list(alerts_collection.find().sort("timestamp", -1))
    for msg in admin_msgs[:5]:
        st.toast(f"📩 {msg.get('message')} ({msg.get('timestamp').strftime('%d %b, %H:%M')})")

    st.subheader("📝 Give Feedback")
    with st.form("feedback_form"):
        name = st.text_input("Your Name")
        feedback = st.text_area("Write your feedback here:")
        rating = st.slider("Rate the Meal ⭐", 1, 5, 3)
        submitted = st.form_submit_button("Submit Feedback")
        if submitted:
            feedback_doc = {
                "name": name,
                "feedback": feedback,
                "rating": rating,
                "timestamp": datetime.now()
            }
            feedback_collection.insert_one(feedback_doc)
            st.success("✅ Thanks for your feedback!")

    st.subheader("📊 Weekly Meal Rating Summary")
    ratings_data = list(feedback_collection.find({"rating": {"$exists": True}}))
    if ratings_data:
        ratings_df = pd.DataFrame(ratings_data)
        ratings_df["timestamp"] = pd.to_datetime(ratings_df["timestamp"])
        ratings_df["day"] = ratings_df["timestamp"].dt.day_name()
        avg_ratings = ratings_df.groupby("day")["rating"].mean().reset_index()
        fig_rating = px.bar(avg_ratings, x="day", y="rating", title="Average Meal Rating by Day", color="day", color_discrete_sequence=px.colors.qualitative.Set2)
        fig_rating.update_layout(yaxis=dict(range=[0, 5]))
        st.plotly_chart(fig_rating, use_container_width=True)

# --- Mess Worker View ---
elif role == "Mess Worker":
    st.header("👷 Mess Worker View")
    show_current_status()

    st.subheader("🔔 Refill Alerts")
    low_tray = df[df["tray_g"] < 300]
    st.write(f"Tray Low Alerts Count: {low_tray.shape[0]}")
    st.dataframe(low_tray[["timestamp", "tray_g"]].tail(10))

    st.subheader("📦 Food Waste Analytics")
    waste_data = df[df["waste_g"] > 0]
    if not waste_data.empty:
        waste_chart = px.histogram(waste_data, x="hour", title="Waste Distribution by Hour")
        st.plotly_chart(waste_chart)

        # Add day-based insight
        day_today = datetime.now().strftime("%A")
        st.info(f"Today is {day_today}. Based on past trends, this day usually sees higher mess crowd or popularity.")
    else:
        st.info("No waste data available.")

    st.subheader("📄 Refill History")
    st.dataframe(df[["timestamp", "tray_g"]].sort_values(by="timestamp", ascending=False).head(20))

    st.subheader("📬 View Feedback from Students")
    fb_data = list(feedback_collection.find({"rating": {"$exists": True}}).sort("timestamp", -1))
    if fb_data:
        fb_df = pd.DataFrame(fb_data)
        fb_df["timestamp"] = pd.to_datetime(fb_df["timestamp"])
        st.dataframe(fb_df[["timestamp", "name", "feedback", "rating"]])
    else:
        st.info("No feedback received yet.")

# --- Mess Admin View ---
elif role == "Mess Admin":
    st.header("🧑‍💼 Mess Admin Dashboard")
    show_current_status()

    st.subheader("📈 Tray Trends by Hour")
    hourly_avg = df.groupby("hour")["tray_g"].mean().reset_index()
    fig2 = px.bar(hourly_avg, x="hour", y="tray_g", title="Average Tray Weight by Hour")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Full Log Overview")
    st.dataframe(df.sort_values(by="timestamp", ascending=False).head(30))

    st.subheader("⚙️ Analytics")
    st.write(f"Total Entries: {df.shape[0]}")
    st.write(f"Average Tray Weight: {df['tray_g'].mean():.2f}g")
    st.write(f"Average Waste: {df['waste_g'].mean():.2f}g")
    st.write(f"Seat Occupied %: {df['seat_occupied'].mean() * 100:.1f}%")

    st.subheader("📢 Send Alert to Students")
    admin_alert = st.text_input("Type your alert message:")
    if st.button("Send Alert"):
        alerts_collection.insert_one({"message": admin_alert, "timestamp": datetime.now()})
        st.success("Alert sent to students.")

    st.subheader("📬 View Feedback from Students")
    fb_data = list(feedback_collection.find({"rating": {"$exists": True}}).sort("timestamp", -1))
    if fb_data:
        fb_df = pd.DataFrame(fb_data)
        fb_df["timestamp"] = pd.to_datetime(fb_df["timestamp"])
        st.dataframe(fb_df[["timestamp", "name", "feedback", "rating"]])

        st.subheader("🌟 Weekly Meal Rating Summary")
        fb_df["day"] = fb_df["timestamp"].dt.day_name()
        avg_ratings = fb_df.groupby("day")["rating"].mean().reset_index()
        fig_rating = px.bar(avg_ratings, x="day", y="rating", title="Average Meal Rating by Day")
        st.plotly_chart(fig_rating)
    else:
        st.info("No feedback received yet.")
