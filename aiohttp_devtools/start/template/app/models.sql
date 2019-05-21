drop schema public cascade;
create schema public;

create table messages (
  id serial primary key,
  username varchar(40) not null,
  message text,
  timestamp timestamptz not null default current_timestamp
);
create index messages_username on messages using btree (username);
create index messages_timestamp on messages using btree (timestamp);
