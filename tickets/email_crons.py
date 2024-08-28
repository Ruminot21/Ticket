import random
import time
from collections import defaultdict, namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed, ALL_COMPLETED, wait

from django.db import connection
from django.utils import timezone
import logging

from events.models import Event
from tickets.models import NewTicketTransfer, NewTicket

DASHES_LINE = '-' * 120


def send_pending_actions_emails(event, context):
    logging.info("Email cron job")
    logging.info("==============")
    logging.info("\n")
    current_event = Event.objects.get(active=True)
    send_pending_actions_emails_for_event(current_event)


def send_pending_actions_emails_for_event(current_event):
    pending_transfers_recipient = get_pending_transfers_recipients(current_event)
    pending_transfers_sender = get_pending_transfers_sender(current_event)
    unsent_tickets = get_unsent_tickets(current_event)

    total_unsent_tickets = sum([holder.pending_to_share_tickets for holder in unsent_tickets])

    logging.info(DASHES_LINE)
    logging.info(f"| {len(pending_transfers_recipient)} Tickets waiting for recipient to create an account")
    logging.info(f"| {total_unsent_tickets} Tickets waiting for the holder to share")
    logging.info(DASHES_LINE)

    start_time = time.perf_counter()
    with (ThreadPoolExecutor() as executor):
        futures = [
                      executor.submit(send_sender_pending_transfers_reminder, transfer, current_event)
                      for transfer
                      in pending_transfers_sender
                  ] + [
                      executor.submit(send_recipient_pending_transfers_reminder, transfer, current_event)
                      for transfer
                      in pending_transfers_recipient
                  ] + [
                      executor.submit(send_unsent_tickets_reminder_email, unsent_ticket, current_event)
                      for unsent_ticket
                      in unsent_tickets
                  ]

    wait(futures, return_when=ALL_COMPLETED)

    logging.info(f"Elapsed time: {time.perf_counter() - start_time:.4f} seconds")


def send_recipient_pending_transfers_reminder(transfer, current_event):
    # TODO: Implement this
    if transfer.max_days_ago % 30 in fibonacci_impares(5):
        logging.info(
            f"sending a notification to the recipient {transfer.tx_to_email} to remember to create an account, you have a pending ticket transfer since {transfer.max_days_ago} days ago. You have time until {current_event.transfers_enabled_until.strftime('%d/%m')}")


def send_sender_pending_transfers_reminder(transfer, current_event):
    #TODO: Implement this
    if transfer.max_days_ago % 30 in fibonacci_impares(5):
        logging.info(
            f"sending a notification to the sender {transfer.tx_from_email} to remember that tickets shared with {transfer.tx_to_emails}, were not accepted yet since {transfer.max_days_ago} days ago. Are you sure they are going to use them? Are the emails correct?. You have time until {current_event.transfers_enabled_until.strftime('%d/%m')}")

    if transfer.max_days_ago == 2:
        logging.info(
            f"sending an SMS notification to the sender {transfer.tx_from_email} to remember that tickets shared with {transfer.tx_to_emails}, were not accepted yet since {transfer.max_days_ago} days ago. Are you sure they are going to use them? Are the emails correct?. You have time until {current_event.transfers_enabled_until.strftime('%d/%m')}")


def send_unsent_tickets_reminder_email(unsent_ticket, current_event):
    # TODO: Implement this
    if unsent_ticket.max_days_ago % 30 in fibonacci_impares(5):
        logging.info(
            f"sending a notification to the holder {unsent_ticket.email} to remember to share the tickets, you have {unsent_ticket.pending_to_share_tickets} pending tickets since {unsent_ticket.max_days_ago} days ago. You have time until {current_event.transfers_enabled_until.strftime('%d/%m')}")


class PendingTransferReceiver:
    def __init__(self, tx_to_email, max_days_ago):
        self.tx_to_email = tx_to_email
        self.max_days_ago = max_days_ago


def get_pending_transfers_recipients(event):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT ntt.tx_to_email, MAX(EXTRACT(DAY FROM (NOW() - ntt.created_at))) as max_days_ago
            FROM tickets_newtickettransfer ntt
            INNER JOIN tickets_newticket nt ON nt.id = ntt.ticket_id
            WHERE ntt.status = 'PENDING' and nt.event_id=%s
            GROUP BY ntt.tx_to_email
        """, [event.id])

        return [PendingTransferReceiver(*row) for row in cursor.fetchall()]


class PendingTransferSender:
    def __init__(self, tx_from_email, tx_to_emails, max_days_ago):
        self.tx_from_email = tx_from_email
        self.tx_to_emails = tx_to_emails
        self.max_days_ago = max_days_ago


def get_pending_transfers_sender(event):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                u.email AS tx_from_email,
                STRING_AGG(DISTINCT email_count.tx_to_email_with_count, ', ') AS tx_to_emails,
                MAX(EXTRACT(DAY FROM (NOW() - ntt.created_at))) AS max_days_ago
            FROM tickets_newtickettransfer ntt
            INNER JOIN tickets_newticket nt ON nt.id = ntt.ticket_id
            INNER JOIN auth_user u ON u.id = ntt.tx_from_id
            INNER JOIN (
                SELECT
                    tx_to_email,
                    CONCAT(tx_to_email, ' (', COUNT(*)::text, ')') AS tx_to_email_with_count
                FROM tickets_newtickettransfer
                WHERE status = 'PENDING'
                GROUP BY tx_to_email
            ) AS email_count ON email_count.tx_to_email = ntt.tx_to_email
            WHERE ntt.status = 'PENDING' AND nt.event_id = %s
            GROUP BY u.email
        """, [event.id])

        # Create TransferDetails objects for each row fetched
        results = cursor.fetchall()

        pending_transfers = []
        for row in results:
            tx_from_email = row[0]
            tx_to_emails_raw = row[1]
            max_days_ago = row[2]

            # Convert tx_to_emails string to an array of dictionaries
            tx_to_emails = []
            for tx_email_with_count in tx_to_emails_raw.split(', '):
                email, count = tx_email_with_count.rsplit(' (', 1)
                count = int(count.rstrip(')'))
                tx_to_emails.append({'tx_to_email': email, 'pending_tickets': count})

            pending_transfers.append(PendingTransferSender(tx_from_email, tx_to_emails, max_days_ago))

        return pending_transfers


class PendingTicketHolder:
    def __init__(self, email, pending_to_share_tickets, max_days_ago):
        self.email = email
        self.pending_to_share_tickets = pending_to_share_tickets
        self.max_days_ago = max_days_ago


def get_unsent_tickets(current_event):
    with connection.cursor() as cursor:
        cursor.execute("""
                select email,
                       count(*)                                                      as pending_to_share_tickets,
                       max(EXTRACT(DAY FROM (NOW() - tickets_newticket.created_at))) as max_days_ago
                
                from tickets_newticket
                
                         inner join auth_user on auth_user.id = tickets_newticket.holder_id
                where owner_id is null
                  and event_id = %s
                group by email
        """, [current_event.id])

        results = cursor.fetchall()

        pending_ticket_holders = []
        for row in results:
            email = row[0]
            pending_to_share_tickets = row[1]
            max_days_ago = row[2]

            # Create an instance of PendingTicketHolder for each row
            pending_ticket_holder = PendingTicketHolder(email, pending_to_share_tickets, max_days_ago)
            pending_ticket_holders.append(pending_ticket_holder)

        return pending_ticket_holders


def fibonacci_impares(n, a=0, b=1, sequence=None):
    if sequence is None:
        sequence = []

    if len(sequence) >= n:
        return sequence

    if a % 2 != 0 and a not in sequence:  # Verifica si el número es impar y no está duplicado
        sequence.append(a)

    return fibonacci_impares(n, b, a + b, sequence)
