CREATE TABLE users (id bigint PRIMARY KEY, email text NOT NULL);
CREATE TABLE orders (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users (id),
    total numeric NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE rates (currency text PRIMARY KEY, rate numeric NOT NULL);
