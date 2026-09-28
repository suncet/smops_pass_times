-- Mail rule action: queue the message, then archive it; the launch agent publishes.
-- Raw mail and diagnostic logs stay local and are never committed to GitHub.
using terms from application "Mail"
 on perform mail action with messages theMessages for rule theRule
  my logEvent("rule started")
  repeat with theMessage in theMessages
   set queued to false
   -- A newly delivered Exchange message may not yet be readable through Mail.
   repeat with attempt from 1 to 4
    set stageName to "read source"
    try
     -- Mail already matched its rule. Validate the saved RFC email rather than
     -- querying sender/subject properties that can be stale during delivery.
     tell application "Mail" to set rawSource to source of theMessage
     if rawSource is missing value or rawSource is "" then error "Message source not ready" number -2700
     set stageName to "validate and save queue"
     my queueMessage(rawSource)
     set queued to true
     my logEvent("message validated and queued")
     exit repeat
    on error number errorNumber
     -- Log only stage and error code, never headers or private message contents.
     my logEvent(stageName & " failed; attempt " & attempt & "; error " & errorNumber)
     if attempt < 4 then delay 5
    end try
   end repeat
   if queued then
    -- Archive failures must never cause an already saved message to be requeued.
    try
     tell application "Mail"
      set sourceMailbox to mailbox of theMessage
      set sourceAccount to account of sourceMailbox
      if (name of sourceAccount is "LASP") and (name of sourceMailbox is "Inbox") then
       move theMessage to mailbox "Archive" of sourceAccount
      end if
     end tell
     my logEvent("archive step complete")
    on error number errorNumber
     my logEvent("archive failed; error " & errorNumber)
    end try
   end if
  end repeat
 end perform mail action with messages
end using terms from

on logEvent(eventText)
 try
  set statePath to (POSIX path of (path to home folder)) & "Library/Application Support/SMOPS Pass Times/"
  set logPath to statePath & "mail-rule.log"
  set timestamp to do shell script "/bin/date -u +%Y-%m-%dT%H:%M:%SZ"
  do shell script "umask 077; /bin/mkdir -p " & quoted form of statePath & "; /bin/echo " & quoted form of (timestamp & " " & eventText) & " >> " & quoted form of logPath
 end try
end logEvent

on queueMessage(rawSource)
 set queuePath to (POSIX path of (path to home folder)) & "Library/Application Support/SMOPS Pass Times/queue/"
 do shell script "/bin/mkdir -p " & quoted form of queuePath & " && /bin/chmod 700 " & quoted form of queuePath
 set messageName to do shell script "/usr/bin/uuidgen"
 set temporaryPath to queuePath & messageName & ".tmp"
 set fileHandle to open for access (POSIX file temporaryPath) with write permission
 try
  set eof fileHandle to 0
  write rawSource to fileHandle as «class utf8»
  close access fileHandle
 on error errorText number errorNumber
  try
   close access fileHandle
  end try
  error errorText number errorNumber
 end try
 -- The publisher repeats validation; this check also prevents archiving invalid mail.
 set publisherPath to (POSIX path of (path to home folder)) & "Library/Application Support/SMOPS Pass Times/publisher/"
 try
  do shell script "cd " & quoted form of publisherPath & " && /usr/bin/python3 -m smops validate " & quoted form of temporaryPath
  do shell script "/bin/chmod 600 " & quoted form of temporaryPath & " && /bin/mv " & quoted form of temporaryPath & " " & quoted form of (queuePath & messageName & ".eml")
 on error errorText number errorNumber
  do shell script "/bin/rm -f " & quoted form of temporaryPath
  error errorText number errorNumber
 end try
end queueMessage
