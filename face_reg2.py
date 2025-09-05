import numpy as np
import os
import redis
import json
import cv2
from insightface.app import FaceAnalysis
from sklearn.metrics import pairwise
from datetime import datetime

# Connect to Redis Client
hostname = 'redis-12236.c330.asia-south1-1.gce.redns.redis-cloud.com'
port = 12236
password = 'VmbHPxUWskFhjrD4joY9LOWdQuecA4nO'

r = redis.StrictRedis(host=hostname, port=port, password=password)

# Configure face analysis
faceapp = FaceAnalysis(name='buffalo_sc', root='insightface_model', providers=['CPUExecutionProvider'])
faceapp.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)

class RegistrationForm:
    def __init__(self):
        self.sample = 0
        
    def reset(self):
        self.sample = 0
        
    def get_embedding(self, frame):
        results = faceapp.get(frame, max_num=1)
        embeddings = None
        for res in results:
            self.sample += 1
            x1, y1, x2, y2 = res['bbox'].astype(int)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
            text = f'samples = {self.sample}'
            cv2.putText(frame, text, (x1, y1), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 0), 2)
            embeddings = res['embedding']
            
        return frame, embeddings
    
    def save_data_in_redis_db(self, form_data):
        # Validate name
        name = form_data.get('person_name', None)
        role = form_data.get('role', None)
        if name is None or name.strip() == '':
            return 'name_false'
        
        # Check if the embedding file exists
        if 'face_embedding.txt' not in os.listdir():
            return 'file_false'
        
        # Load embeddings from "face_embedding.txt"
        x_array = np.loadtxt('face_embedding.txt', dtype=np.float32)
        
        # Convert into array (proper shape)
        received_samples = int(x_array.size / 512)
        x_array = x_array.reshape(received_samples, 512)
        x_array = np.asarray(x_array)
        
        # Calculate mean embeddings
        x_mean = x_array.mean(axis=0)
        x_mean = x_mean.astype(np.float32)
        x_mean_bytes = x_mean.tobytes()
        
        # Serialize form data
        form_data_serialized = json.dumps({
            'phone_number': form_data.get('phone_number', ''),
            'address_firstline': form_data.get('address_firstline', ''),
            'address_area': form_data.get('address_area', ''),
            'pincode': form_data.get('pincode', ''),
            'state': form_data.get('state', ''),
            'age': form_data.get('age', 0),
            'gender': form_data.get('gender', ''),
            'aadhaar_pan': form_data.get('aadhaar_pan', '')
        })
        form_data_serialized_bytes = form_data_serialized.encode('utf-8')
        
        # Save to Redis
        key = f'{name}@{role}'
        r.hset(name='academy:register', key=key, value=x_mean_bytes)
        r.hset(name='academy:register:details', key=key, value=form_data_serialized_bytes)
        
        os.remove('face_embedding.txt')
        self.reset()
        
        return True
