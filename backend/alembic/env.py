import sys
from logging.config import fileConfig
from pathlib import Path
from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.app.core.config import settings
from backend.app.models.base import Base
# Import all models for autogenerate
from backend.app.models.user import User
from backend.app.models.consent import ConsentRecord
from backend.app.models.audit import AuditLog
from backend.app.models.appointment import Appointment
from backend.app.models.doctor import Doctor
from backend.app.models.patient import Patient
from backend.app.models.clinic import Clinic
from backend.app.models.verification import DoctorDocument, VerificationReview
from backend.app.models.schedule import DoctorAvailability, DoctorLeave
from backend.app.models.payment import PaymentTransaction
from backend.app.models.cancellation_policy import CancellationPolicy

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from settings
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
