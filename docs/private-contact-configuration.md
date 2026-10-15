# Private contact-routing configuration

Contact resolution does not distribute a directory of real people, municipal mailboxes or telephone numbers. Supply a private contact bundle with `send_queue`, `official_channels` and `source_observed_as_of`.

Verify contact ownership and permissible use before generating a routing packet. The first two channels provide primary and secondary defaults; include at least one `phone` escalation channel. Each channel requires a type and value; attribution fields can record the source and verification date. Keep the completed bundle and generated packets outside source control. Examples and tests use reserved domains and synthetic telephone numbers.

This command generates local review artifacts. It does not authorize sending requests or publishing contact information.
