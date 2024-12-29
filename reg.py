import streamlit as st
import cv2
import numpy as np
from streamlit_webrtc import webrtc_streamer
import face_reg2
import av

st.set_page_config(page_title='Registration form', layout='centered')
st.subheader('Registration form')

# Initialize registration form
registration_form = face_reg2.RegistrationForm()

# Step 1: Collect person details
person_name = st.text_input(label='Name', placeholder='First and Last Name')
role = st.selectbox(label='Select your role', options=('Supervisor', 'Manager', 'Staff'))
phone_number = st.text_input(label='Phone Number', placeholder='Enter your phone number')
address_firstline = st.text_input(label='Address (First Line)', placeholder='Street, Building, etc.')
address_area = st.text_input(label='Area', placeholder='Locality, Landmark, etc.')
pincode = st.text_input(label='Pincode', placeholder='Enter pincode')
state = st.text_input(label='State', placeholder='Enter your state')
age = st.number_input(label='Age', min_value=18, max_value=100, step=1)
gender = st.selectbox(label='Gender', options=('Male', 'Female', 'Other'))
aadhaar_pan = st.text_input(label='Aadhaar Number / PAN Number', placeholder='Enter Aadhaar or PAN number')

# Create a dictionary to store form data
form_data = {
    'person_name': person_name,
    'role': role,
    'phone_number': phone_number,
    'address_firstline': address_firstline,
    'address_area': address_area,
    'pincode': pincode,
    'state': state,
    'age': age,
    'gender': gender,
    'aadhaar_pan': aadhaar_pan
}

# Step 2: Collect facial embedding of the person
def video_callback_func(frame):
    img = frame.to_ndarray(format="bgr24")  # 3D numpy array
    reg_img, embedding = registration_form.get_embedding(img)
    
    # Save the embedding data into local computer txt
    if embedding is not None:
        with open('face_embedding.txt', mode='ab') as f:
            np.savetxt(f, embedding)
    
    return av.VideoFrame.from_ndarray(reg_img, format="bgr24")

webrtc_streamer(key="Registration", video_frame_callback=video_callback_func, rtc_configuration={
    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
})


# Step 3: Save the data in the Redis database
if st.button('Submit'):
    return_val = registration_form.save_data_in_redis_db(form_data)
    print('saved in redis')
    
    if return_val == True:
        st.success(f'{person_name} registered successfully')
        
        # Option 1: Provide a link to the Flask login page
        st.markdown("[Go to Login Page](http://127.0.0.1:5000)")
        
        # Option 2: Automatically redirect to the Flask login page
        # Uncomment this if you prefer an automatic redirect
        # js = """
        # <script type="text/javascript">
        #     window.location.href = "http://localhost:5000/login";
        # </script>
        # """
        # st.markdown(js, unsafe_allow_html=True)
    
    elif return_val == 'name_false':
        st.error('Please enter the name: Name cannot be empty or spaces')
    elif return_val == 'file_false':
        st.error('face_embedding.txt is not found. Please refresh the page and execute it again.')
