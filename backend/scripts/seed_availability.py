import asyncio
import datetime
import uuid
from sqlalchemy import select, delete
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.user import User
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.schedule import DoctorAvailability
from backend.app.services.schedule_engine import generate_slots

async def seed():
    async with AsyncSessionLocal() as session:
        # Find all verified and online doctors
        stmt = select(Doctor).where(
            Doctor.verification_status == VerificationStatus.VERIFIED
        )
        doctors = list((await session.execute(stmt)).scalars().all())
        print(f"Found {len(doctors)} verified doctors.")

        seeded_count = 0
        for doc in doctors:
            # Check if clinic exists
            clinic_stmt = select(Clinic).where(Clinic.doctor_id == doc.user_id)
            clinic = (await session.execute(clinic_stmt)).scalar_one_or_none()
            if not clinic:
                clinic = Clinic(
                    id=uuid.uuid4(),
                    doctor_id=doc.user_id,
                    name=f"{doc.full_name}'s Clinic",
                    address="100 Metro Healthcare Ave",
                    city="Mumbai",
                    locality="Bandra West",
                    pincode="400050",
                    contact_number="+91 9876543210",
                    latitude=19.0596,
                    longitude=72.8295,
                )
                session.add(clinic)
                await session.flush()

            # Delete existing availability for clean seed
            await session.execute(
                delete(DoctorAvailability).where(DoctorAvailability.doctor_id == doc.user_id)
            )

            # Insert Monday through Sunday (0 to 6)
            for dow in range(7):
                # Morning Shift: 09:00 to 13:00
                m_avail = DoctorAvailability(
                    id=uuid.uuid4(),
                    doctor_id=doc.user_id,
                    clinic_id=clinic.id,
                    day_of_week=dow,
                    start_time=datetime.time(9, 0, 0),
                    end_time=datetime.time(13, 0, 0),
                    slot_duration_minutes=15,
                    buffer_minutes=5,
                    mode="both",
                    is_active=True,
                )
                session.add(m_avail)

                # Afternoon/Evening Shift: 14:00 to 18:00
                e_avail = DoctorAvailability(
                    id=uuid.uuid4(),
                    doctor_id=doc.user_id,
                    clinic_id=clinic.id,
                    day_of_week=dow,
                    start_time=datetime.time(14, 0, 0),
                    end_time=datetime.time(18, 0, 0),
                    slot_duration_minutes=15,
                    buffer_minutes=5,
                    mode="both",
                    is_active=True,
                )
                session.add(e_avail)

            seeded_count += 1

        await session.commit()
        print(f"Successfully seeded 7-day availability for {seeded_count} doctors!")

        # Verify slot generation for sample doctor
        test_doc_id = doctors[0].user_id
        today = datetime.date.today()
        slots = await generate_slots(
            doctor_id=test_doc_id,
            query_date=today,
            mode="in_person",
            session=session,
        )
        print(f"Sample test doctor: {doctors[0].full_name} ({test_doc_id}) on {today}:")
        print(f"Total available slots generated: {len(slots)}")
        if slots:
            print(f"First slot: {slots[0].start_time.isoformat()} - {slots[0].end_time.isoformat()} (₹{slots[0].fee_amount})")
            print(f"Last slot: {slots[-1].start_time.isoformat()} - {slots[-1].end_time.isoformat()}")

if __name__ == "__main__":
    asyncio.run(seed())
