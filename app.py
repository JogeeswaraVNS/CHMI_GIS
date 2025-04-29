import folium,math
from streamlit_folium import st_folium
import streamlit as st
from azure.cosmos import CosmosClient
import plotly.express as px
import pandas as pd
from fuzzywuzzy import process
from collections import defaultdict



# # --- Cosmos DB Configuration ---
import streamlit as st

PRIMARY_KEY = st.secrets["PRIMARY_KEY"]

COSMOS_URL = st.secrets["COSMOS_URL"]
DATABASE_NAME = st.secrets["DATABASE_NAME"]
CONTAINER_NAME = st.secrets["CONTAINER_NAME"]
USER_CONTAINER_NAME = st.secrets["USER_CONTAINER_NAME"]



client = CosmosClient(COSMOS_URL, credential=PRIMARY_KEY)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)
user_container = database.get_container_client(USER_CONTAINER_NAME)


# Fetch data from Cosmos DB
query = "SELECT * FROM c"
items = list(container.query_items(query=query, enable_cross_partition_query=True))

user_query = "SELECT * FROM c"
user_items = list(user_container.query_items(query=user_query, enable_cross_partition_query=True))


# Function to remove trailing whitespace in dictionary keys and array values
def trim_trailing_spaces(data):
    if isinstance(data, dict):
        # Recursively process each key-value pair in the dictionary
        return {key: trim_trailing_spaces(value) for key, value in data.items()}
    elif isinstance(data, list):
        # Process each element in the array
        return [trim_trailing_spaces(element) for element in data]
    elif isinstance(data, str):
        # Remove trailing spaces from string
        return data.strip()
    else:
        # Return the data as-is if it's not a dict, list, or string
        return data

def fuzzy_match(mandal):
    match, score = process.extractOne(mandal, mandals)
    if score > 80:  # Threshold to accept matches (adjust as needed)
        return match
    else:
        return mandal 

# Apply the trim function to remove trailing spaces
items = [trim_trailing_spaces(item) for item in items]

mandals=['Manthani','Ramagiri','Thadicherla']

# Streamlit App Configuration
st.set_page_config(layout="wide")
st.markdown("""<style>.title-wrapper { text-align: center; }</style>""", unsafe_allow_html=True)

# Main Title
st.markdown("<div class='title-wrapper'><h2>Cattle Health Monitoring Intelligence Dashboard</h2></div>", unsafe_allow_html=True)

# --- User Authentication ---
st.sidebar.title("Login")

# Predefined user credentials (username: password)
USER_CREDENTIALS = {}

# Generate credentials dynamically from veta00 to veta25
for i in user_items:
    user_id = i['cid']  # Format numbers with leading zeros, e.g., veta00, veta01, etc.
    password = i['password']
    USER_CREDENTIALS[user_id] = password

username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Login"):
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        st.sidebar.success(f"Welcome, {username}!")
        st.session_state["logged_in"] = True
    else:
        st.sidebar.error("Invalid username or password!")

if st.session_state.get("logged_in"):
    option = st.sidebar.selectbox("Select Visualization Type", ["Point Map", "Pin Map", "Cattle Count","Vaccination"])

    # Initializing counters and farmers dictionary
    farmers_dict = {}
    total_cows = 0
    total_bulls = 0

    # Populate farmers_dict with counts and calculate total cows and bulls
    for item in items:
        if "farmer_name" in item:
            farmer_name = item["farmer_name"].strip()
        elif "owner_name" in item:
            farmer_name = item["owner_name"].strip()
        else:
            farmer_name = "Not found"
        if farmer_name not in farmers_dict:
            farmers_dict[farmer_name] = {"cows": 0, "bulls": 0}

        if item["gender"] == "Male":
            farmers_dict[farmer_name]["bulls"] += 1
            total_bulls += 1
        else:
            farmers_dict[farmer_name]["cows"] += 1
            total_cows += 1

    # Display total farmers, cows, and bulls in the sidebar
    st.sidebar.markdown(f"<h4>Total No. of Farmers: {len(farmers_dict)}</h4>", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Total No. of Cows:** {total_cows}")
    st.sidebar.markdown(f"**Total No. of Bulls:** {total_bulls}")
    
    # Collapsible farmers list with cow and bull counts under each farmer
    with st.sidebar.expander("View Farmers List"):
        for farmer, counts in farmers_dict.items():
            st.write(f"**{farmer}:** {counts['cows']} cows, {counts['bulls']} bulls")



    # Color Palette for Pin Map
    COLOR_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    # Create a session state for unique colors (lat, lon-based)
    if "circle_color_map" not in st.session_state:
        st.session_state.circle_color_map = {}

    # --- Point Map ---
    if option == "Point Map":
        st.markdown("<h4>Point Map - Constituency-wise Labels</h4>", unsafe_allow_html=True)

        with st.spinner('Loading map data...'):
            location_data = items

        if location_data:
            m = folium.Map(zoom_start=7)
            bounds, color_index = [], 0

            # Iterate and create individual circle markers with color coding
            for loc in location_data:
                lat = float(loc.get("latitude", 0))
                lon = float(loc.get("longitude", 0))
                
                if 15.8 <= lat <= 19.9 and 77.0 <= lon <= 81.0:  # Telangana bounds
                    popup_content = (f"<b>District:</b> {loc.get("district", "Unknown")}<br>"
                                     f"<b>Mandal:</b> {loc.get("mandal", "Unknown")}<br>"
                                     f"<b>Village:</b> {loc.get("village", "Unknown")}<br><br>"
                                     f"<img src='{loc.get("photo_frontb", None)}' width='100%'><br>")

                    # Assign a unique color for the point
                    if (lat, lon) not in st.session_state.circle_color_map:
                        st.session_state.circle_color_map[(lat, lon)] = COLOR_PALETTE[color_index % len(COLOR_PALETTE)]
                        color_index += 1

                    unique_color = st.session_state.circle_color_map[(lat, lon)]
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=8,
                        color=unique_color,
                        fill=True,
                        fill_color=unique_color,
                        fill_opacity=0.7,
                        popup=folium.Popup(popup_content, max_width=300)
                    ).add_to(m)

                    bounds.append([lat, lon])

            # Fit map bounds to include all points
            if bounds:
                m.fit_bounds(bounds)
            st_folium(m, width=None, height=600, use_container_width=True)
        else:
            st.warning("No valid data found!")

    # --- Pin Map ---
    elif option == "Pin Map":
        st.markdown("<h4>Pin Map - Click a Pin for Cattle & Farmer Details</h4>", unsafe_allow_html=True)

        with st.spinner('Loading map data...'):
            location_data = items

        if location_data:
            m = folium.Map(zoom_start=7)
            bounds, color_index = [], 0

            for loc in location_data:
                lat = float(loc.get("latitude", 0))
                lon = float(loc.get("longitude", 0))
                if 15.8 <= lat <= 19.9 and 77.0 <= lon <= 81.0:  # Telangana bounds
                    farmer_name = loc.get("farmer_name", "Unknown Farmer")
                    popup_content = (f"<b>Farmer Name:</b> {farmer_name}<br>"
                                    f"<b>Ear TagID:</b> {loc.get('ear_tag_id', 'Unknown')}<br>"
                                    f"<b>Breed Type:</b> {loc.get('breed_type', ['Unknown'])[0] if isinstance(loc.get('breed_type', 'Unknown'), list) else loc.get('breed_type', 'Unknown')}<br>"
                                    f"<b>Age:</b> {loc.get('age', 'Unknown')} <b>Gender:</b> {loc.get('gender', 'Unknown')}<br><br>"
                                    f"<img src='{loc.get('photo_frontb', '')}' width='100%'><br>")


                    # Assign color if not already mapped
                    if (lat, lon) not in st.session_state.circle_color_map:
                        st.session_state.circle_color_map[(lat, lon)] = COLOR_PALETTE[color_index % len(COLOR_PALETTE)]
                        color_index += 1

                    unique_color = st.session_state.circle_color_map[(lat, lon)]
                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.Icon(color="blue", icon_color=unique_color, icon='info-sign'),
                        popup=folium.Popup(popup_content, max_width=300)
                    ).add_to(m)

                    bounds.append([lat, lon])

            if bounds:
                m.fit_bounds(bounds)
            st_folium(m, width=None, height=600, use_container_width=True)
        else:
            st.warning("No valid data found!")

    # --- Cattle Count ---
    elif option == "Cattle Count":
        st.subheader("Cattle Distribution Mandal-wise")

        location_data = items  # Replace this with your actual list of cow data

        if location_data:
            # Convert the list of dictionaries into a DataFrame
            df = pd.DataFrame(location_data)

            # Clean the 'mandal' column by removing leading and trailing spaces using str.strip()
            df['mandal'] = df['mandal'].str.strip()

            # Apply fuzzy matching to clean the 'mandal' names
            df['mandal'] = df['mandal'].apply(fuzzy_match)

            # Group by the cleaned 'mandal' column and count entries (cattle)
            cattle_count_by_mandal = df.groupby('mandal').size().reset_index(name='Cattle Count')

            # Group by mandal and count the number of entries (cattle)
            cattle_count_by_mandal = df.groupby('mandal').size().reset_index(name='Cattle Count')

            # Extract mandals and their respective cattle counts
            mandals = cattle_count_by_mandal['mandal']
            cattle_counts = cattle_count_by_mandal['Cattle Count']

            # Create grouped bar plots
            group_size = 5
            num_groups = math.ceil(len(mandals) / group_size)

            for i in range(num_groups):
                start_idx = i * group_size
                end_idx = min(start_idx + group_size, len(mandals))

                group_data = {
                    'Mandal': mandals[start_idx:end_idx],
                    'Cattle Count': cattle_counts[start_idx:end_idx]
                }

                fig = px.bar(
                    group_data,
                    x='Mandal',
                    y='Cattle Count',
                    color='Cattle Count',
                    color_continuous_scale='viridis',
                    labels={'Cattle Count': 'Number of Cattle'},
                    title=f"Cattle Distribution (Mandals {start_idx + 1} - {end_idx})"
                )

                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig)

        else:
            st.warning("No valid cattle distribution data found!")

    
    elif option == "Vaccination":
        st.subheader("Vaccination Heat Map")
        vaccine = st.selectbox("Select Vaccination", ["BQ", "FMD", "Brucellosis", "LSD", "Thellorosis", "Others"], key='vaccine')
        filtered_data = [item for item in items if vaccine in item["vaccinations"]]  # Filter cattle by selected vaccine

        if filtered_data:
            st.write(f"Cattle vaccinated with **{vaccine}**: **{len(filtered_data)}**")


            m = folium.Map(zoom_start=7)
            bounds, color_index = [], 0
            COLOR_PALETTE = ['blue', 'green', 'red', 'purple', 'orange']

            if "circle_color_map" not in st.session_state:
                st.session_state.circle_color_map = {}

            for loc in filtered_data:
                lat, lon = float(loc["latitude"]), float(loc["longitude"])
                if 15.8 <= lat <= 19.9 and 77.0 <= lon <= 81.0:  # Telangana bounds
                    farmer_name = loc.get("farmer_name", "Unknown Farmer")
                    popup_content = (f"<b>Farmer Name:</b> {farmer_name}<br>"
                                    f"<b>Ear TagID:</b> {loc['ear_tag_id']}<br>"
                                    f"<b>Breed Type:</b> {loc['breed_type'][0]}<br>"
                                    f"<b>Vaccinations:</b> {', '.join(loc['vaccinations'])}<br>"
                                    f"<b>Age:</b> {loc['age']} <b>Gender:</b> {loc['gender']}<br><br>"
                                    f"<img src='{loc['photo_frontb']}' width='100%'><br>")

                    # Assign color if not already mapped
                    if (lat, lon) not in st.session_state.circle_color_map:
                        st.session_state.circle_color_map[(lat, lon)] = COLOR_PALETTE[color_index % len(COLOR_PALETTE)]
                        color_index += 1

                    unique_color = st.session_state.circle_color_map[(lat, lon)]
                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.Icon(color="blue", icon_color=unique_color, icon='info-sign'),
                        popup=folium.Popup(popup_content, max_width=300)
                    ).add_to(m)

                    bounds.append([lat, lon])

            if bounds:
                m.fit_bounds(bounds)
            st_folium(m, width=None, height=600, use_container_width=True)

            mandal_counts = defaultdict(lambda: {"total": 0, "vaccinated": 0})
            for item in items:
                mandal = item.get("mandal", "Unknown")
                mandal=fuzzy_match(mandal)
                mandal_counts[mandal]["total"] += 1
                if vaccine in item["vaccinations"]:
                    mandal_counts[mandal]["vaccinated"] += 1

            # Prepare data for pie chart and display total/vaccinated count in popup
            pie_data = []
            for mandal, counts in mandal_counts.items():
                if counts["total"] > 0:
                    percentage = (counts["vaccinated"] / counts["total"]) * 100
                    popup_detail = f"Total Cattle: {counts['total']}, Vaccinated Cattle: {counts['vaccinated']}"
                    pie_data.append({"Mandal": f"{mandal} ({popup_detail})", "Percentage Vaccinated": percentage})

            df = pd.DataFrame(pie_data)
            if not df.empty:
                fig = px.pie(df, values='Percentage Vaccinated', names='Mandal',
                            title=f'Percentage of Cattle Vaccinated with {vaccine} by Mandal',
                            hover_data=["Percentage Vaccinated"], hole=0.4)
                fig.update_traces(textinfo="label", pull=[0.1 if i == 0 else 0 for i in range(len(df))])
                st.plotly_chart(fig)
            else:
                st.warning("No data available for pie chart.")

        else:
            st.warning(f"No cattle found vaccinated for {vaccine}.")

            


else:
    # Display message to users before login
    st.markdown("<h4 style='text-align: center; color: red;'>Please log in to access the dashboard!</h4>", unsafe_allow_html=True)