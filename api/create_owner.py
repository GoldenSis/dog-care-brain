#!/usr/bin/env python3
"""Explicit operator bootstrap for one owner, without demo dogs or email delivery.

Run against the intended private DC_DATA_DIR; never expose this as a web route.
Existing accounts are preserved. Client access is linked by the owner in the app.
"""
import argparse
import server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    args=parser.parse_args()
    email=args.email.strip().lower()
    if not server.EMAIL_RE.fullmatch(email) or len(email)>255:
        parser.error('a valid owner email is required')
    if server.login_delivery.demo_signup_enabled():
        parser.error('turn off DC_ALLOW_DEMO_SIGNUP to create a real empty owner account')
    server.init()
    with server._lock,server.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT role FROM user WHERE email=?',(email,)).fetchone()
        if existing and existing['role']!='owner':
            parser.error('this email already has a different role; no account was changed')
        uid,bid=server.ensure_account(c,email)
    print(f'Owner ready: user {uid}, business {bid}. Existing records preserved; no email sent.')

if __name__=='__main__':main()
