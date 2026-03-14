## branches
```sql
CREATE TABLE branches (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    phone VARCHAR(50),
    timezone VARCHAR(100) NOT NULL DEFAULT 'Europe/London',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## staff
```sql
CREATE TABLE staff (
    id BIGSERIAL PRIMARY KEY,

    full_name VARCHAR(255) NOT NULL,

    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'doctor', 'marketer', 'operator')),

    specialty VARCHAR(100),

    phone VARCHAR(50),
    email VARCHAR(255),

    can_take_chats BOOLEAN DEFAULT FALSE,
    can_take_appointments BOOLEAN DEFAULT FALSE,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## staff_branches
```sql
CREATE TABLE staff_branches (
    staff_id BIGINT REFERENCES staff(id) ON DELETE CASCADE,
    branch_id BIGINT REFERENCES branches(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (staff_id, branch_id)
);
```

## staff_schedules
```sql
CREATE TABLE staff_schedules (
    id BIGSERIAL PRIMARY KEY,
    staff_id BIGINT NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    branch_id BIGINT REFERENCES branches(id) ON DELETE SET NULL,

    weekday SMALLINT NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from DATE,
    valid_to DATE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (end_time > start_time),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE INDEX idx_staff_schedules_staff_weekday
ON staff_schedules(staff_id, weekday);
```

## staff_schedule_exceptions
```sql
CREATE TABLE staff_schedule_exceptions (
    id BIGSERIAL PRIMARY KEY,
    staff_id BIGINT NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    branch_id BIGINT REFERENCES branches(id) ON DELETE SET NULL,

    exception_date DATE NOT NULL,
    start_time TIME,
    end_time TIME,

    exception_type VARCHAR(50) NOT NULL,
    -- day_off / custom_hours / vacation / sick_leave

    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        (exception_type = 'day_off' AND start_time IS NULL AND end_time IS NULL)
        OR
        (exception_type IN ('custom_hours') AND start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)
        OR
        (exception_type IN ('vacation', 'sick_leave') AND start_time IS NULL AND end_time IS NULL)
    )
);
```

## channels
```sql
CREATE TABLE channels (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## contacts
```sql
CREATE TABLE contacts (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    birth_date DATE,
    notes TEXT,
    source_channel_id BIGINT REFERENCES channels(id) ON DELETE SET NULL,
    lifecycle_stage VARCHAR(50) NOT NULL CHECK (lifecycle_stage IN ('lead', 'qualified', 'booked', 'patient', 'inactive')) DEFAULT 'lead',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## service_categories
```sql
CREATE TABLE service_categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## services
```sql
CREATE TABLE services (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id BIGINT REFERENCES service_categories(id) ON DELETE SET NULL,
    description TEXT,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    base_price NUMERIC(10,2) NOT NULL CHECK (base_price >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## appointment_statuses
```sql
CREATE TABLE appointment_statuses (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## appointments
```sql
CREATE TABLE appointments (
    id BIGSERIAL PRIMARY KEY,
    contact_id BIGINT NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
    provider_staff_id BIGINT REFERENCES staff(id) ON DELETE SET NULL,
    branch_id BIGINT REFERENCES branches(id) ON DELETE SET NULL,

    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,

    status_id BIGINT NOT NULL REFERENCES appointment_statuses(id) ON DELETE RESTRICT,
    channel_id BIGINT REFERENCES channels(id) ON DELETE SET NULL,
    comment TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (end_at > start_at)
);
```

## appointment_services
```sql
CREATE TABLE appointment_services (
    id BIGSERIAL PRIMARY KEY,
    appointment_id BIGINT NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    service_id BIGINT NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0)
);
```

## conversation_statuses
```sql
CREATE TABLE conversation_statuses (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## conversations
```sql
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    contact_id BIGINT REFERENCES contacts(id) ON DELETE SET NULL,
    channel_id BIGINT REFERENCES channels(id) ON DELETE SET NULL,
    external_chat_id VARCHAR(255),
    status_id BIGINT NOT NOLL REFERENCES conversation_statuses(id) ON DELETE RESTRICT,
    operator_id BIGINT REFERENCES staff(id) ON DELETE SET NULL,
    handoff_status VARCHAR(50) NOT NULL DEFAULT 'none',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CHECK (handoff_status IN ('none', 'requested', 'assigned', 'in_progress', 'resolved'))
);
```

## messages
```sql
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction VARCHAR(20) NOT NULL CHECK(direction IN ('inbound', 'outbound')),
    sender_type VARCHAR(50) NOT NULL CHECK(sender_type IN ('contact', 'bot', 'ai_assistant', 'staff', 'system', 'integration')),
    message_text TEXT,
    message_type VARCHAR(50) NOT NULL CHECK(message_type IN ('text', 'image', 'file', 'audio')) DEFAULT 'text',
    external_message_id VARCHAR(255),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```sql
CREATE INDEX idx_staff_branches_branch_id ON staff_branches(branch_id);

CREATE INDEX idx_staff_schedule_exceptions_staff_id
ON staff_schedule_exceptions(staff_id);

CREATE INDEX idx_staff_schedule_exceptions_exception_date
ON staff_schedule_exceptions(exception_date);

CREATE INDEX idx_contacts_phone ON contacts(phone);
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_lifecycle_stage ON contacts(lifecycle_stage);

CREATE INDEX idx_services_category_id ON services(category_id);

CREATE INDEX idx_appointments_contact_id ON appointments(contact_id);
CREATE INDEX idx_appointments_provider_staff_id ON appointments(provider_staff_id);
CREATE INDEX idx_appointments_branch_id ON appointments(branch_id);
CREATE INDEX idx_appointments_status_id ON appointments(status_id);
CREATE INDEX idx_appointments_start_at ON appointments(start_at);

CREATE INDEX idx_conversations_contact_id ON conversations(contact_id);
CREATE INDEX idx_conversations_channel_id ON conversations(channel_id);
CREATE INDEX idx_conversations_status_id ON conversations(status_id);
CREATE INDEX idx_conversations_operator_id ON conversations(operator_id);
CREATE INDEX idx_conversations_external_chat_id ON conversations(external_chat_id);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_sent_at ON messages(sent_at);
```