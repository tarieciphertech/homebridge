-- HomeBridge landlord/tenant property finance ledger (PostgreSQL)
-- Additive schema: does not alter existing RentPayment or platform Payment records.
BEGIN;

CREATE TABLE IF NOT EXISTS property_charge (
    id SERIAL PRIMARY KEY,
    tenancy_id INTEGER NOT NULL REFERENCES tenancy(id),
    property_id INTEGER NOT NULL REFERENCES property(id),
    landlord_id INTEGER NOT NULL REFERENCES "user"(id),
    tenant_id INTEGER NOT NULL REFERENCES "user"(id),
    charge_type VARCHAR(30) NOT NULL DEFAULT 'other',
    title VARCHAR(180) NOT NULL,
    description TEXT,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    due_date DATE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_id INTEGER NOT NULL REFERENCES "user"(id)
);

CREATE INDEX IF NOT EXISTS ix_property_charge_tenancy_id ON property_charge(tenancy_id);
CREATE INDEX IF NOT EXISTS ix_property_charge_property_id ON property_charge(property_id);
CREATE INDEX IF NOT EXISTS ix_property_charge_landlord_id ON property_charge(landlord_id);
CREATE INDEX IF NOT EXISTS ix_property_charge_tenant_id ON property_charge(tenant_id);

CREATE TABLE IF NOT EXISTS property_transaction (
    id SERIAL PRIMARY KEY,
    charge_id INTEGER NOT NULL REFERENCES property_charge(id),
    tenancy_id INTEGER NOT NULL REFERENCES tenancy(id),
    property_id INTEGER NOT NULL REFERENCES property(id),
    landlord_id INTEGER NOT NULL REFERENCES "user"(id),
    tenant_id INTEGER NOT NULL REFERENCES "user"(id),
    submitted_by_id INTEGER NOT NULL REFERENCES "user"(id),
    transaction_type VARCHAR(20) NOT NULL DEFAULT 'payment',
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(10) NOT NULL,
    method VARCHAR(30) NOT NULL DEFAULT 'bank_transfer',
    reference VARCHAR(100),
    proof_file VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    notes TEXT,
    submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by_id INTEGER REFERENCES "user"(id),
    reviewed_at TIMESTAMP WITHOUT TIME ZONE,
    review_notes TEXT
);

CREATE INDEX IF NOT EXISTS ix_property_transaction_charge_id ON property_transaction(charge_id);
CREATE INDEX IF NOT EXISTS ix_property_transaction_tenancy_id ON property_transaction(tenancy_id);
CREATE INDEX IF NOT EXISTS ix_property_transaction_property_id ON property_transaction(property_id);
CREATE INDEX IF NOT EXISTS ix_property_transaction_landlord_id ON property_transaction(landlord_id);
CREATE INDEX IF NOT EXISTS ix_property_transaction_tenant_id ON property_transaction(tenant_id);
CREATE INDEX IF NOT EXISTS ix_property_transaction_status ON property_transaction(status);

COMMIT;
