-- Enable ltree for hierarchical taxonomy queries
CREATE EXTENSION IF NOT EXISTS ltree;

-- Enable uuid-ossp for UUIDv4 generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Taxonomy table — stores the versioned 5-level hierarchy
CREATE TABLE IF NOT EXISTS taxonomy (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path        LTREE NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    version     TEXT NOT NULL DEFAULT '1.0',
    deprecated  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS taxonomy_path_gist ON taxonomy USING GIST (path);

-- Seed Signal Alpha domains (Authentication & Onboarding)
INSERT INTO taxonomy (path, label, version) VALUES
    ('Authentication',                          'Authentication',        '1.0'),
    ('Authentication.Login',                    'Login',                 '1.0'),
    ('Authentication.Login.PasswordReset',      'Password Reset',        '1.0'),
    ('Authentication.Login.SsoFailure',         'SSO Failure',           '1.0'),
    ('Authentication.Login.AccountLocked',      'Account Locked',        '1.0'),
    ('Authentication.Mfa',                      'Multi-Factor Auth',     '1.0'),
    ('Authentication.Mfa.SetupFailure',         'MFA Setup Failure',     '1.0'),
    ('Authentication.Mfa.VerificationFailure',  'MFA Verify Failure',    '1.0'),
    ('Onboarding',                              'Onboarding',            '1.0'),
    ('Onboarding.Registration',                 'Registration',          '1.0'),
    ('Onboarding.Registration.EmailVerification','Email Verification',   '1.0'),
    ('Onboarding.Registration.AccountCreation', 'Account Creation',      '1.0'),
    ('Onboarding.Setup',                        'Setup',                 '1.0'),
    ('Onboarding.Setup.ProfileConfiguration',   'Profile Configuration', '1.0'),
    ('Onboarding.Training',                     'Training',              '1.0'),
    ('Billing',                                 'Billing',               '1.0'),
    ('Billing.Payment',                         'Payment',               '1.0'),
    ('Billing.Payment.ProcessingError',         'Payment Processing Error','1.0'),
    ('Billing.Subscription',                    'Subscription',          '1.0'),
    ('Billing.Subscription.Cancellation',       'Cancellation',          '1.0'),
    ('Compliance',                              'Compliance',            '1.0'),
    ('Compliance.Popia',                        'POPIA',                 '1.0'),
    ('Compliance.Popia.DataAccessRequest',      'Data Access Request',   '1.0'),
    ('Reporting',                               'Reporting',             '1.0'),
    ('Reporting.Dashboards',                    'Dashboards',            '1.0'),
    ('Reporting.Dashboards.Export',             'Export',                '1.0')
ON CONFLICT (path) DO NOTHING;
