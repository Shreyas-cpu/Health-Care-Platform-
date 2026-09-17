"""
Seed script for Chhatrapati Sambhaji Nagar (Aurangabad), Maharashtra.
Populates verified doctors, clinics, schedules, chemists, patients, appointments,
prescriptions, and patient reviews matching the schema and business rules.
"""

import asyncio
import datetime
import decimal
import hashlib
import json
import os
import sys
import uuid
from decimal import Decimal

# Ensure project root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy import delete, select
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.redis import get_redis_client
from backend.app.models.appointment import Appointment, AppointmentMode, AppointmentStatus, PaymentStatus
from backend.app.models.chemist import Chemist
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.drug import DrugMaster, seed_default_drugs
from backend.app.models.patient import Patient
from backend.app.models.prescription import Prescription, PrescriptionItem
from backend.app.models.review import Review, ReviewStatus
from backend.app.models.schedule import DoctorAvailability
from backend.app.models.user import User, UserRole

CITY_NAME = "Chhatrapati Sambhaji Nagar"

DOCTORS_DATA = [
    {
        "full_name": "Dr. Sachin Kulkarni",
        "email": "dr.sachin.kulkarni.csn@healthcare.local",
        "phone": "+919422000001",
        "reg_no": "MMC/2008/04/1120",
        "council": "Maharashtra Medical Council",
        "specialty": "General Physician",
        "experience": 16,
        "fee": Decimal("500.00"),
        "rating": Decimal("4.90"),
        "reviews": 38,
        "gender": "Male",
        "bio": "Senior Consultant Physician specializing in lifestyle disease management, diabetes mellitus, hypertension, and infectious diseases in Marathwada region.",
        "clinic_name": "Kulkarni Care Clinic & Diagnostic Centre",
        "locality": "Kranti Chowk",
        "address": "Plot 14, Station Road, Opp. Divisional Commissioner Office, Kranti Chowk",
        "pincode": "431001",
        "lat": 19.8736000,
        "lon": 75.3245000,
        "clinic_phone": "+912402334001",
    },
    {
        "full_name": "Dr. Neha Deshmukh",
        "email": "dr.neha.deshmukh.csn@healthcare.local",
        "phone": "+919422000002",
        "reg_no": "MMC/2012/06/1842",
        "council": "Maharashtra Medical Council",
        "specialty": "Pediatrics",
        "experience": 12,
        "fee": Decimal("600.00"),
        "rating": Decimal("4.85"),
        "reviews": 29,
        "gender": "Female",
        "bio": "Consultant Pediatrician and Neonatologist. Dedicated to child growth monitoring, vaccinations, infant nutrition, and acute pediatric care.",
        "clinic_name": "Little Smiles Pediatric Clinic",
        "locality": "CIDCO",
        "address": "Sector N-4, Near Cidco Bus Stand & Cannaught Garden, CIDCO",
        "pincode": "431003",
        "lat": 19.8824000,
        "lon": 75.3619000,
        "clinic_phone": "+912402482002",
    },
    {
        "full_name": "Dr. Rohan Bhalerao",
        "email": "dr.rohan.bhalerao.csn@healthcare.local",
        "phone": "+919422000003",
        "reg_no": "MMC/2006/03/0951",
        "council": "Maharashtra Medical Council",
        "specialty": "Cardiology",
        "experience": 18,
        "fee": Decimal("900.00"),
        "rating": Decimal("4.95"),
        "reviews": 46,
        "gender": "Male",
        "bio": "Interventional Cardiologist with extensive experience in preventive cardiology, ECG, Echocardiography, post-angioplasty rehab, and coronary risk assessment.",
        "clinic_name": "Hridayam Heart & Chest Clinic",
        "locality": "Seven Hills",
        "address": "3rd Floor, Metro Square, Jalna Road, Seven Hills",
        "pincode": "431005",
        "lat": 19.8741000,
        "lon": 75.3524000,
        "clinic_phone": "+912402356003",
    },
    {
        "full_name": "Dr. Pooja Shinde",
        "email": "dr.pooja.shinde.csn@healthcare.local",
        "phone": "+919422000004",
        "reg_no": "MMC/2014/09/2718",
        "council": "Maharashtra Medical Council",
        "specialty": "Dermatology",
        "experience": 10,
        "fee": Decimal("700.00"),
        "rating": Decimal("4.80"),
        "reviews": 24,
        "gender": "Female",
        "bio": "Consultant Dermatologist and Trichologist specializing in clinical dermatology, acne scarring, eczema, psoriasis, and medical hair restoration.",
        "clinic_name": "Aura Skin & Hair Clinic",
        "locality": "Nirala Bazar",
        "address": "Shop 102, City Centre Complex, Main Road, Nirala Bazar",
        "pincode": "431001",
        "lat": 19.8821000,
        "lon": 75.3278000,
        "clinic_phone": "+912402321004",
    },
    {
        "full_name": "Dr. Amit V. Patil",
        "email": "dr.amit.patil.csn@healthcare.local",
        "phone": "+919422000005",
        "reg_no": "MMC/2009/02/0644",
        "council": "Maharashtra Medical Council",
        "specialty": "Orthopedics",
        "experience": 15,
        "fee": Decimal("750.00"),
        "rating": Decimal("4.88"),
        "reviews": 33,
        "gender": "Male",
        "bio": "Orthopedic Surgeon specializing in arthroscopy, sports trauma, joint pain management, fracture treatment, and arthritis rehabilitation.",
        "clinic_name": "Sanjivani Bone & Joint Clinic",
        "locality": "Samarth Nagar",
        "address": "Row House 3, Behind Varad Ganesh Mandir, Samarth Nagar",
        "pincode": "431001",
        "lat": 19.8845000,
        "lon": 75.3312000,
        "clinic_phone": "+912402345005",
    },
    {
        "full_name": "Dr. Snehal Kadam",
        "email": "dr.snehal.kadam.csn@healthcare.local",
        "phone": "+919422000006",
        "reg_no": "MMC/2010/05/1330",
        "council": "Maharashtra Medical Council",
        "specialty": "Gynecology",
        "experience": 14,
        "fee": Decimal("650.00"),
        "rating": Decimal("4.92"),
        "reviews": 41,
        "gender": "Female",
        "bio": "Obstetrician and Gynecologist focused on antenatal maternal care, high-risk pregnancy monitoring, PCOS/PCOD management, and menopause health.",
        "clinic_name": "Vatsalya Maternity & Nursing Clinic",
        "locality": "Garkheda",
        "address": "Plot 82, Sutgirni Chowk, Garkheda Parisar",
        "pincode": "431009",
        "lat": 19.8632000,
        "lon": 75.3481000,
        "clinic_phone": "+912402451006",
    },
    {
        "full_name": "Dr. Vikramaditya Jadhav",
        "email": "dr.vikram.jadhav.csn@healthcare.local",
        "phone": "+919422000007",
        "reg_no": "DCI/MAH/2015/0821",
        "council": "Maharashtra Dental Council",
        "specialty": "Dentistry",
        "experience": 9,
        "fee": Decimal("400.00"),
        "rating": Decimal("4.75"),
        "reviews": 21,
        "gender": "Male",
        "bio": "Dental Surgeon & Endodontist providing painless root canal treatments, cosmetic teeth whitening, crown/bridge installations, and routine scaling.",
        "clinic_name": "Crown Dental Care & Implant Center",
        "locality": "Osmanpura",
        "address": "1st Floor, Tapadiya Pride, Near Sant Eknath Rang Mandir, Osmanpura",
        "pincode": "431005",
        "lat": 19.8692000,
        "lon": 75.3271000,
        "clinic_phone": "+912402360007",
    },
    {
        "full_name": "Dr. Rajeshwari Joshi",
        "email": "dr.rajeshwari.joshi.csn@healthcare.local",
        "phone": "+919422000008",
        "reg_no": "MMC/2011/08/2155",
        "council": "Maharashtra Medical Council",
        "specialty": "ENT",
        "experience": 13,
        "fee": Decimal("600.00"),
        "rating": Decimal("4.82"),
        "reviews": 26,
        "gender": "Female",
        "bio": "ENT Specialist treating chronic sinusitis, allergic rhinitis, tonsillitis, vertigo, tinnitus, and pediatric ear infections.",
        "clinic_name": "Swara ENT & Hearing Solutions",
        "locality": "Cannaught Place",
        "address": "Office 204, Prozone Trade Hub, Cannaught Place, CIDCO",
        "pincode": "431003",
        "lat": 19.8835000,
        "lon": 75.3642000,
        "clinic_phone": "+912402488008",
    },
    {
        "full_name": "Dr. Anand Kale",
        "email": "dr.anand.kale.csn@healthcare.local",
        "phone": "+919422000009",
        "reg_no": "MMC/2007/01/0432",
        "council": "Maharashtra Medical Council",
        "specialty": "Ophthalmology",
        "experience": 17,
        "fee": Decimal("500.00"),
        "rating": Decimal("4.89"),
        "reviews": 35,
        "gender": "Male",
        "bio": "Consultant Ophthalmologist and Phaco Surgeon specializing in cataract surgery, glaucoma detection, dry eye disease, and computerized vision testing.",
        "clinic_name": "Drishti Netralaya & Retina Centre",
        "locality": "Shahnoorwadi",
        "address": "Bungalow No. 5, Behind Dargah Road, Shahnoorwadi",
        "pincode": "431005",
        "lat": 19.8685000,
        "lon": 75.3402000,
        "clinic_phone": "+912402341009",
    },
    {
        "full_name": "Dr. Priyadarshini More",
        "email": "dr.priya.more.csn@healthcare.local",
        "phone": "+919422000010",
        "reg_no": "MMC/2016/11/3890",
        "council": "Maharashtra Medical Council",
        "specialty": "General Physician",
        "experience": 8,
        "fee": Decimal("450.00"),
        "rating": Decimal("4.78"),
        "reviews": 19,
        "gender": "Female",
        "bio": "Family Physician focused on routine health screenings, geriatric monitoring, preventive medicine, seasonal viral syndromes, and metabolic health.",
        "clinic_name": "Prerana Family Clinic",
        "locality": "Beed Bypass",
        "address": "Shop 4, Greenfield Enclave, Near Bajaj Hospital, Beed Bypass",
        "pincode": "431010",
        "lat": 19.8512000,
        "lon": 75.3418000,
        "clinic_phone": "+912402500010",
    },
    {
        "full_name": "Dr. Sandeep Gaikwad",
        "email": "dr.sandeep.gaikwad.csn@healthcare.local",
        "phone": "+919422000011",
        "reg_no": "MMC/2005/07/0812",
        "council": "Maharashtra Medical Council",
        "specialty": "Neurology",
        "experience": 19,
        "fee": Decimal("1000.00"),
        "rating": Decimal("4.96"),
        "reviews": 52,
        "gender": "Male",
        "bio": "Senior Consultant Neurologist handling migraine management, post-stroke recovery, neuropathy, Parkinson's disease, and epileptic disorders.",
        "clinic_name": "NeuroCare Clinic & Diagnostic Lab",
        "locality": "Seven Hills",
        "address": "Plot 22, Jalna Road, Near Akashwani Tower, Seven Hills",
        "pincode": "431005",
        "lat": 19.8755000,
        "lon": 75.3498000,
        "clinic_phone": "+912402377011",
    },
    {
        "full_name": "Dr. Manisha Rathi",
        "email": "dr.manisha.rathi.csn@healthcare.local",
        "phone": "+919422000012",
        "reg_no": "MMC/2013/04/1560",
        "council": "Maharashtra Medical Council",
        "specialty": "Dermatology",
        "experience": 11,
        "fee": Decimal("650.00"),
        "rating": Decimal("4.83"),
        "reviews": 27,
        "gender": "Female",
        "bio": "Specialist in dermatopathology, pediatric skin conditions, allergic contact dermatitis, fungal skin infections, and vitiligo care.",
        "clinic_name": "SkinPlus Clinic",
        "locality": "CIDCO",
        "address": "Avishkar Colony, Near N-6 Cricket Stadium, CIDCO",
        "pincode": "431003",
        "lat": 19.8860000,
        "lon": 75.3670000,
        "clinic_phone": "+912402485012",
    },
]

CHEMISTS_DATA = [
    {
        "name": "Sambhaji Medical & General Stores",
        "phone": "+919422180001",
        "email": "sambhaji.medical@healthcare.local",
        "license": "MH-AUR-2023-20B-10821",
        "locality": "Kranti Chowk",
        "address": "Shop 2, Ground Floor, Station Road, Near Kranti Chowk Flyover",
        "pincode": "431001",
    },
    {
        "name": "Apollo Pharmacy CIDCO Cannaught",
        "phone": "+919422180002",
        "email": "apollo.cidco@healthcare.local",
        "license": "MH-AUR-2022-20B-11540",
        "locality": "CIDCO",
        "address": "Shop 12, Cannaught Shopping Center, CIDCO N-4",
        "pincode": "431003",
    },
    {
        "name": "Wellness Forever 24x7 Chemist",
        "phone": "+919422180003",
        "email": "wellness.sevenhills@healthcare.local",
        "license": "MH-AUR-2024-20B-19412",
        "locality": "Seven Hills",
        "address": "Plot 18, Jalna Road, Opposite Seven Hills Hotel",
        "pincode": "431005",
    },
    {
        "name": "City Medico & Surgical Suppliers",
        "phone": "+919422180004",
        "email": "city.medico@healthcare.local",
        "license": "MH-AUR-2021-20B-08340",
        "locality": "Nirala Bazar",
        "address": "City Market Lane, Near Central Bank, Nirala Bazar",
        "pincode": "431001",
    },
    {
        "name": "Sanjeevani Pharmacy Garkheda",
        "phone": "+919422180005",
        "email": "sanjeevani.garkheda@healthcare.local",
        "license": "MH-AUR-2023-20B-12933",
        "locality": "Garkheda",
        "address": "Shop 5, Suyog Complex, Sutgirni Road, Garkheda Parisar",
        "pincode": "431009",
    },
    {
        "name": "MGM Care Chemist",
        "phone": "+919422180006",
        "email": "mgm.chemist@healthcare.local",
        "license": "MH-AUR-2020-20B-06219",
        "locality": "CIDCO",
        "address": "Near MGM Medical Campus, Gate 2, N-6 CIDCO",
        "pincode": "431003",
    },
    {
        "name": "Bajaj Hospital Care Chemist",
        "phone": "+919422180007",
        "email": "bajaj.chemist@healthcare.local",
        "license": "MH-AUR-2022-20B-14561",
        "locality": "Beed Bypass",
        "address": "Opp. Kamalnayan Bajaj Hospital, Beed Bypass Road",
        "pincode": "431010",
    },
    {
        "name": "Balaji Medicals & Surgicals",
        "phone": "+919422180008",
        "email": "balaji.medicals@healthcare.local",
        "license": "MH-AUR-2023-20B-13890",
        "locality": "Osmanpura",
        "address": "Main Road, Near Sant Eknath Hall, Osmanpura",
        "pincode": "431005",
    },
]

PATIENTS_DATA = [
    {
        "full_name": "Rahul Waghmare",
        "email": "rahul.waghmare.csn@healthcare.local",
        "phone": "+919422700001",
        "gender": "Male",
        "dob": datetime.date(1992, 4, 15),
    },
    {
        "full_name": "Sunita Salve",
        "email": "sunita.salve.csn@healthcare.local",
        "phone": "+919422700002",
        "gender": "Female",
        "dob": datetime.date(1985, 8, 22),
    },
    {
        "full_name": "Prashant Shinde",
        "email": "prashant.shinde.csn@healthcare.local",
        "phone": "+919422700003",
        "gender": "Male",
        "dob": datetime.date(1978, 11, 3),
    },
    {
        "full_name": "Kavita Kulkarni",
        "email": "kavita.kulkarni.csn@healthcare.local",
        "phone": "+919422700004",
        "gender": "Female",
        "dob": datetime.date(1996, 2, 19),
    },
    {
        "full_name": "Ganesh Muley",
        "email": "ganesh.muley.csn@healthcare.local",
        "phone": "+919422700005",
        "gender": "Male",
        "dob": datetime.date(2001, 7, 30),
    },
    {
        "full_name": "Vaishali Jadhav",
        "email": "vaishali.jadhav.csn@healthcare.local",
        "phone": "+919422700006",
        "gender": "Female",
        "dob": datetime.date(1989, 12, 11),
    },
]


async def seed_aurangabad():
    print(f"Starting seed for {CITY_NAME} (Aurangabad)...")
    async with AsyncSessionLocal() as session:
        # 1. Ensure DrugMaster is populated
        drug_count = await seed_default_drugs(session)
        if drug_count:
            print(f"Seeded {drug_count} default drugs in drug_master.")

        # 2. Seed Patients
        created_patients = []
        for pdata in PATIENTS_DATA:
            stmt = select(User).where(User.phone_number == pdata["phone"])
            existing_user = (await session.execute(stmt)).scalar_one_or_none()
            if not existing_user:
                p_user = User(
                    id=uuid.uuid4(),
                    phone_number=pdata["phone"],
                    email=pdata["email"],
                    role=UserRole.PATIENT,
                    is_active=True,
                )
                session.add(p_user)
                await session.flush()

                p_profile = Patient(
                    user_id=p_user.id,
                    full_name=pdata["full_name"],
                    gender=pdata["gender"],
                    date_of_birth=pdata["dob"],
                )
                session.add(p_profile)
                created_patients.append((p_user, p_profile))
            else:
                p_prof = (await session.execute(select(Patient).where(Patient.user_id == existing_user.id))).scalar_one_or_none()
                created_patients.append((existing_user, p_prof))

        print(f"Patients ready: {len(created_patients)}")

        # 3. Seed Doctors, Clinics, Availability
        created_doctors = []
        for ddata in DOCTORS_DATA:
            stmt = select(User).where(User.phone_number == ddata["phone"])
            doc_user = (await session.execute(stmt)).scalar_one_or_none()
            if not doc_user:
                doc_user = User(
                    id=uuid.uuid4(),
                    phone_number=ddata["phone"],
                    email=ddata["email"],
                    role=UserRole.DOCTOR,
                    is_active=True,
                )
                session.add(doc_user)
                await session.flush()

            stmt_doc = select(Doctor).where(Doctor.user_id == doc_user.id)
            doc = (await session.execute(stmt_doc)).scalar_one_or_none()
            if not doc:
                doc = Doctor(
                    user_id=doc_user.id,
                    full_name=ddata["full_name"],
                    medical_reg_number=ddata["reg_no"],
                    council_name=ddata["council"],
                    specialty=ddata["specialty"],
                    years_experience=ddata["experience"],
                    bio=ddata["bio"],
                    gender=ddata["gender"],
                    in_person_fee=ddata["fee"],
                    video_fee=Decimal("0.00"),
                    verification_status=VerificationStatus.VERIFIED,
                    listing_online=True,
                    video_enabled=False,
                    average_rating=ddata["rating"],
                    review_count=ddata["reviews"],
                )
                session.add(doc)
                await session.flush()

            # Clinic
            stmt_clinic = select(Clinic).where(Clinic.doctor_id == doc.user_id)
            clinic = (await session.execute(stmt_clinic)).scalar_one_or_none()
            if not clinic:
                clinic = Clinic(
                    id=uuid.uuid4(),
                    doctor_id=doc.user_id,
                    name=ddata["clinic_name"],
                    address=ddata["address"],
                    city=CITY_NAME,
                    locality=ddata["locality"],
                    pincode=ddata["pincode"],
                    contact_number=ddata["clinic_phone"],
                    latitude=ddata["lat"],
                    longitude=ddata["lon"],
                )
                session.add(clinic)
                await session.flush()

            # Weekly Availability
            await session.execute(delete(DoctorAvailability).where(DoctorAvailability.doctor_id == doc.user_id))
            for dow in range(7):  # Mon-Sun
                # Morning Shift: 09:00 - 13:00
                session.add(DoctorAvailability(
                    id=uuid.uuid4(),
                    doctor_id=doc.user_id,
                    clinic_id=clinic.id,
                    day_of_week=dow,
                    start_time=datetime.time(9, 0),
                    end_time=datetime.time(13, 0),
                    slot_duration_minutes=15,
                    buffer_minutes=5,
                    mode="both",
                    is_active=True,
                ))
                # Evening Shift: 17:00 - 20:30
                session.add(DoctorAvailability(
                    id=uuid.uuid4(),
                    doctor_id=doc.user_id,
                    clinic_id=clinic.id,
                    day_of_week=dow,
                    start_time=datetime.time(17, 0),
                    end_time=datetime.time(20, 30),
                    slot_duration_minutes=15,
                    buffer_minutes=5,
                    mode="both",
                    is_active=True,
                ))

            created_doctors.append((doc_user, doc, clinic))

        print(f"Doctors & Clinics seeded: {len(created_doctors)}")

        # 4. Seed Chemists
        created_chemists = []
        for i, cdata in enumerate(CHEMISTS_DATA):
            stmt = select(User).where(User.phone_number == cdata["phone"])
            c_user = (await session.execute(stmt)).scalar_one_or_none()
            if not c_user:
                c_user = User(
                    id=uuid.uuid4(),
                    phone_number=cdata["phone"],
                    email=cdata["email"],
                    role=UserRole.CHEMIST,
                    is_active=True,
                )
                session.add(c_user)
                await session.flush()

            stmt_chem = select(Chemist).where(Chemist.user_id == c_user.id)
            chem = (await session.execute(stmt_chem)).scalar_one_or_none()
            assigned_clinic = created_doctors[i % len(created_doctors)][2] if created_doctors else None
            if not chem:
                chem = Chemist(
                    id=uuid.uuid4(),
                    user_id=c_user.id,
                    pharmacy_name=cdata["name"],
                    license_number=cdata["license"],
                    clinic_id=assigned_clinic.id if assigned_clinic else None,
                    address=cdata["address"],
                    city=CITY_NAME,
                    locality=cdata["locality"],
                    pincode=cdata["pincode"],
                    contact_number=cdata["phone"],
                    is_active=True,
                )
                session.add(chem)
                await session.flush()
            created_chemists.append(chem)

        print(f"Chemists seeded: {len(created_chemists)}")

        # 5. Seed Realistic Appointments, Prescriptions & Reviews
        today = datetime.datetime.now(datetime.timezone.utc)
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)

        # Sample clinical consultations
        sample_cases = [
            {
                "doc_idx": 0,  # Dr. Sachin Kulkarni (General Physician)
                "patient_idx": 0,
                "diagnosis": "Acute upper respiratory tract infection with low-grade pyrexia",
                "notes": "Throat congestion noted. Advised warm saline gargles, adequate hydration, and resting for 48 hours.",
                "items": [
                    ("Crocin 650", "650mg", "TID", 3, "After meals for fever"),
                    ("Pan 40", "40mg", "OD", 5, "Before breakfast"),
                    ("Cetzine", "10mg", "HS", 5, "At bedtime for rhinitis"),
                ],
                "rating": 5,
                "review": "Dr. Sachin Kulkarni was extremely attentive. Listened to my symptoms carefully and explained the treatment clearly. Kranti Chowk clinic is very well maintained!",
            },
            {
                "doc_idx": 1,  # Dr. Neha Deshmukh (Pediatrics)
                "patient_idx": 1,
                "diagnosis": "Pediatric acute viral bronchitis and mild dehydration",
                "notes": "Chest clear of wheezing. Encouraged ORS fluids and frequent small meals.",
                "items": [
                    ("Crocin Drops", "100mg/ml", "SOS", 3, "Only if temp exceeds 100 F"),
                    ("Amoxicillin Oral Suspension", "125mg/5ml", "TID", 5, "Complete the 5-day course"),
                ],
                "rating": 5,
                "review": "Dr. Neha is wonderful with toddlers! Made my daughter feel at ease immediately. Excellent clinic in CIDCO N-4.",
            },
            {
                "doc_idx": 2,  # Dr. Rohan Bhalerao (Cardiology)
                "patient_idx": 2,
                "diagnosis": "Essential hypertension (Stage 1) and mild hyperlipidemia",
                "notes": "Resting BP 142/90 mmHg. Advised 30 mins brisk walking daily and low-sodium diet. Repeat lipid profile in 6 weeks.",
                "items": [
                    ("Telmisartan", "40mg", "OD", 30, "Morning after breakfast"),
                    ("Atorvastatin", "10mg", "HS", 30, "At bedtime"),
                ],
                "rating": 5,
                "review": "Superb cardiologist on Jalna Road. Very reassuring and thorough ECG review. Highly recommended.",
            },
            {
                "doc_idx": 3,  # Dr. Pooja Shinde (Dermatology)
                "patient_idx": 3,
                "diagnosis": "Grade 2 Acne Vulgaris and post-inflammatory erythema",
                "notes": "Prescribed non-comedogenic sunscreen and gentle foaming cleanser. Avoid picking lesions.",
                "items": [
                    ("Azithral 500", "500mg", "OD", 3, "Pulse therapy for 3 days"),
                    ("Clindamycin Gel", "1%", "BD", 14, "Topical application on active spots"),
                ],
                "rating": 4,
                "review": "Great experience at Aura Skin Clinic in Nirala Bazar. Doctor gave practical skincare routine without pushing unnecessary procedures.",
            },
            {
                "doc_idx": 4,  # Dr. Amit Patil (Orthopedics)
                "patient_idx": 4,
                "diagnosis": "Right knee patellofemoral pain syndrome",
                "notes": "Quadriceps strengthening exercises demonstrated. Cold compress twice daily.",
                "items": [
                    ("Aceclofenac + Paracetamol", "100mg/325mg", "BD", 5, "After food"),
                    ("Pan 40", "40mg", "OD", 5, "Before breakfast"),
                ],
                "rating": 5,
                "review": "Accurate diagnosis and excellent physiotherapy advice. Dr. Patil avoided unnecessary MRI scans. Samarth Nagar location is easy to reach.",
            },
        ]

        for i, case in enumerate(sample_cases):
            doc_user, doc, clinic = created_doctors[case["doc_idx"]]
            pat_user, pat_profile = created_patients[case["patient_idx"]]

            # Past completed appointment
            past_start = yesterday.replace(hour=10 + i, minute=0, second=0, microsecond=0)
            past_end = past_start + datetime.timedelta(minutes=15)

            # Check if appointment exists
            appt_stmt = select(Appointment).where(
                Appointment.doctor_id == doc_user.id,
                Appointment.patient_id == pat_user.id,
                Appointment.slot_start == past_start,
            )
            appt = (await session.execute(appt_stmt)).scalar_one_or_none()
            if not appt:
                appt = Appointment(
                    id=uuid.uuid4(),
                    patient_id=pat_user.id,
                    doctor_id=doc_user.id,
                    clinic_id=clinic.id,
                    mode=AppointmentMode.IN_PERSON,
                    status=AppointmentStatus.COMPLETED,
                    slot_start=past_start,
                    slot_end=past_end,
                    fee_amount=doc.in_person_fee,
                    payment_status=PaymentStatus.CAPTURED,
                    reminder_sent=True,
                )
                session.add(appt)
                await session.flush()

            # Prescription
            presc_stmt = select(Prescription).where(Prescription.appointment_id == appt.id)
            presc = (await session.execute(presc_stmt)).scalar_one_or_none()
            if not presc:
                chemist = created_chemists[i % len(created_chemists)]
                sig_data = f"{doc.medical_reg_number}:{appt.id}:{past_start.isoformat()}"
                sig_hash = hashlib.sha256(sig_data.encode()).hexdigest()

                presc = Prescription(
                    id=uuid.uuid4(),
                    appointment_id=appt.id,
                    doctor_id=doc.user_id,
                    patient_id=pat_user.id,
                    diagnosis=case["diagnosis"],
                    clinical_notes=case["notes"],
                    issued_at=past_end,
                    chemist_id=chemist.id,
                    digital_signature=f"MMC-EDIG-SIG-{sig_hash[:24]}",
                    digital_signature_timestamp=past_end,
                    dispense_status="dispensed",
                    dispensed_at=past_end + datetime.timedelta(minutes=25),
                    dispensed_by_chemist_id=chemist.id,
                )
                session.add(presc)
                await session.flush()

                for med_name, dos, freq, dur, inst in case["items"]:
                    session.add(PrescriptionItem(
                        id=uuid.uuid4(),
                        prescription_id=presc.id,
                        drug_name=med_name,
                        dosage=dos,
                        frequency=freq,
                        duration_days=dur,
                        instructions=inst,
                    ))

            # Review
            rev_stmt = select(Review).where(Review.appointment_id == appt.id)
            rev = (await session.execute(rev_stmt)).scalar_one_or_none()
            if not rev:
                rev = Review(
                    id=uuid.uuid4(),
                    appointment_id=appt.id,
                    doctor_id=doc.user_id,
                    patient_id=pat_user.id,
                    rating=case["rating"],
                    review_text=case["review"],
                    status=ReviewStatus.PUBLISHED,
                )
                session.add(rev)

            # Upcoming confirmed appointment for tomorrow
            fut_start = tomorrow.replace(hour=11 + i, minute=0, second=0, microsecond=0)
            fut_end = fut_start + datetime.timedelta(minutes=15)
            fut_appt_stmt = select(Appointment).where(
                Appointment.doctor_id == doc_user.id,
                Appointment.patient_id == pat_user.id,
                Appointment.slot_start == fut_start,
            )
            fut_appt = (await session.execute(fut_appt_stmt)).scalar_one_or_none()
            if not fut_appt:
                session.add(Appointment(
                    id=uuid.uuid4(),
                    patient_id=pat_user.id,
                    doctor_id=doc_user.id,
                    clinic_id=clinic.id,
                    mode=AppointmentMode.IN_PERSON,
                    status=AppointmentStatus.CONFIRMED,
                    slot_start=fut_start,
                    slot_end=fut_end,
                    fee_amount=doc.in_person_fee,
                    payment_status=PaymentStatus.CAPTURED,
                    reminder_sent=False,
                ))

        await session.commit()
        print("Database commit successful.")

    # 6. Flush Redis query cache so new doctors appear immediately in searches
    client = get_redis_client()
    try:
        keys = [key async for key in client.scan_iter(match="cache:search:*")]
        if keys:
            await client.delete(*keys)
            print(f"Purged {len(keys)} Redis search cache keys.")
    except Exception as e:
        print(f"Redis cache flush notice: {e}")
    finally:
        await client.aclose()

    print(f"✅ Seeding complete for {CITY_NAME} (Aurangabad)!")


if __name__ == "__main__":
    asyncio.run(seed_aurangabad())
