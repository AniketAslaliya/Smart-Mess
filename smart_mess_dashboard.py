import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
import numpy as np

# --- MongoDB Connection ---
client = MongoClient("mongodb+srv://mess:123@smartmess.o14pepz.mongodb.net/?retryWrites=true&w=majority&appName=SmartMess")
db = client["iot_test"]
collection = db["messages"]
alerts_collection = db["alerts"]
feedback_collection = db["feedback"]

# --- Load and Process Data ---
data = list(collection.find())
if not data:
    st.warning("No data found in MongoDB collection.")
    st.stop()

df = pd.DataFrame(data)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["hour"] = df["timestamp"].dt.hour
df["value"] = pd.to_numeric(df["message"], errors="coerce")

# --- Role-Based Menu ---
st.title("Smart Mess System Dashboard")
role = st.sidebar.selectbox("Select User Role", ["Student", "Mess Worker", "Mess Admin"])

# --- Student View ---
if role == "Student":
    st.header("📱 Student View")

    st.subheader("📊 Tray Level Over Time")
    fig = px.line(df, x="timestamp", y="value", title="Tray Usage Trend")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🚦 Current Mess Status")
    latest_value = df.sort_values("timestamp", ascending=False).iloc[0]["value"]
    if latest_value < 300:
        st.error("🔴 Tray Low — Avoid visiting now")
    elif latest_value < 700:
        st.warning("🟠 Tray Medium — Visit Soon")
    else:
        st.success("🟢 Tray Full — Visit Now")

    st.subheader("🪑 Seat Occupancy Info")
    seat_occupied = np.random.randint(60, 100)  # Placeholder
    total_seats = 100
    seat_vacant = total_seats - seat_occupied
    st.metric("Vacant Seats", seat_vacant)

    st.subheader("📈 Peak Crowd Hours")
    peak_hour = df["hour"].value_counts().idxmax()
    st.info(f"🕓 Most crowded around: {peak_hour}:00 hrs")

    st.subheader("📢 Messages from Mess Admin")
    admin_msgs = list(alerts_collection.find().sort("timestamp", -1))
    for msg in admin_msgs[:5]:
        st.warning(f"📩 {msg.get('message')} ({msg.get('timestamp')})")

    st.subheader("📝 Give Feedback")
    name = st.text_input("Your Name")
    feedback = st.text_area("Write your feedback here:")
    rating = st.select_slider("Rate the Meal ⭐", options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], value="⭐⭐⭐")
    if st.button("Submit Feedback"):
        feedback_doc = {
            "name": name,
            "feedback": feedback,
            "rating": len(rating),
            "timestamp": datetime.now()
        }
        feedback_collection.insert_one(feedback_doc)
        st.success("Thanks for your feedback!")

    st.subheader("📊 Weekly Meal Rating Summary")
    ratings_data = list(feedback_collection.find({"rating": {"$exists": True}}))
    if ratings_data:
        ratings_df = pd.DataFrame(ratings_data)
        ratings_df["timestamp"] = pd.to_datetime(ratings_df["timestamp"])
        ratings_df["day"] = ratings_df["timestamp"].dt.day_name()
        avg_ratings = ratings_df.groupby("day")["rating"].mean().reset_index()
        fig_rating = px.bar(avg_ratings, x="day", y="rating", title="Average Meal Rating by Day")
        st.plotly_chart(fig_rating)

# --- Mess Worker View ---
elif role == "Mess Worker":
    st.header("👷 Mess Worker View")

    st.subheader("🔔 Refill Alerts")
    low_tray = df[df["value"] < 300]
    st.write(f"Tray Low Alerts Count: {low_tray.shape[0]}")
    st.dataframe(low_tray[["timestamp", "value"]].tail(10))

    st.subheader("📦 Food Waste Analytics")
    waste_data = df[df["value"] < 100]  # Placeholder for actual waste sensor
    if not waste_data.empty:
        st.write(f"Total waste records: {waste_data.shape[0]}")
        waste_chart = px.histogram(waste_data, x="hour", title="Waste Distribution by Hour")
        st.plotly_chart(waste_chart)
    else:
        st.info("No waste data available.")

    st.subheader("📄 Refill History")
    st.dataframe(df[["timestamp", "value"]].sort_values(by="timestamp", ascending=False).head(20))

    st.subheader("📬 View Feedback from Students")
    fb_data = list(feedback_collection.find().sort("timestamp", -1))
    if fb_data:
        fb_df = pd.DataFrame(fb_data)
        st.dataframe(fb_df[["timestamp", "name", "feedback", "rating"]])
    else:
        st.info("No feedback received yet.")

# --- Mess Admin View ---
elif role == "Mess Admin":
    st.header("🧑‍💼 Mess Admin Dashboard")

    st.subheader("📈 FSR Trends by Hour")
    hourly_avg = df.groupby("hour")["value"].mean().reset_index()
    fig2 = px.bar(hourly_avg, x="hour", y="value", title="Average Tray Pressure by Hour")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Full Log Overview")
    st.dataframe(df.sort_values(by="timestamp", ascending=False).head(30))

    st.subheader("⚙️ Analytics")
    st.write(f"Total Entries: {df.shape[0]}")
    st.write(f"Average Tray Level: {df['value'].mean():.2f}")
    st.write(f"Peak Tray Level: {df['value'].max():.2f}")
    st.write(f"Lowest Tray Level: {df['value'].min():.2f}")

    st.subheader("📢 Send Alert to Students")
    admin_alert = st.text_input("Type your alert message:")
    if st.button("Send Alert"):
        alerts_collection.insert_one({"message": admin_alert, "timestamp": datetime.now()})
        st.success("Alert sent to students.")

    st.subheader("📬 View Feedback from Students")
    fb_data = list(feedback_collection.find().sort("timestamp", -1))
    if fb_data:
        fb_df = pd.DataFrame(fb_data)
        st.dataframe(fb_df[["timestamp", "name", "feedback", "rating"]])

        st.subheader("🌟 Weekly Meal Rating Summary")
        fb_df["timestamp"] = pd.to_datetime(fb_df["timestamp"])
        fb_df["day"] = fb_df["timestamp"].dt.day_name()
        avg_ratings = fb_df.groupby("day")["rating"].mean().reset_index()
        fig_rating = px.bar(avg_ratings, x="day", y="rating", title="Average Meal Rating by Day")
        st.plotly_chart(fig_rating)
    else:
        st.info("No feedback received yet.")
