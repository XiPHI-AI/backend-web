# Folder Structure Spec:

- We have kept the date identifier post the event id since we might have region specific policies for events ( happening in specific zones ) and there we can take action on those events as a whole or have policies defined on storage at that level.
- We have kept the date identifer before the user, since it will help us mimic the traffic coming in a day by just looking at the storage with this convention and we can do  time centric operations per day etc. We can also see the interactions of the event over time by just logically looking at the structure on storage layer. 
- The audio and text are kept separate so that in future (if required) analytics on the text can be done separately without trying to reorganize the storage structure


## structure for text/json blob

`transcripts/{generated_by}/text/{org_id}/{event_id}/{yyyy-mm-dd}/{user_id}/{sequence_no}/{file_name}.json`

with the following definitions:
- `generated_by` : this the origin , for now it will be eleven_labs but in future we can use model_id when we possibly move to our own tts or stt 
- `org_id` : this is the registered event organizer. 
- `event_id` : this is the registered event for that organizer
- `{yyyy-md-dd}` : this is based of the metadata/start_time_unix_secs from the webhook payload, converted to the timezone format of the location the event is happening in. 
- `user_id` : unique id generated in our system per user -- a user might have multiple registration_ids and each registration is associated with one event_id.
- `sequence_no`: this could be derived from our database for each user but adds unnecessary overhead, so we should just fall back on metadata/start_time_unix_secs information in metadata for this. this will also allow us to sort the incoming converstaions based on order directly using filesystem sort etc as well. 
- `file_name` : this will depend on the generated_by provider however for elevenlabs we can use the conversation_id from elevenlabs for now.


## structure on audio blob

`transcripts/{generated_by}/audio/{org_id}/{event_id}/{yyyy-mm-dd}/{user_id}/{sequence_no}/{file_name}.{mp3}`

Same as defined for text blob except separte at root with *audio*, we have kept this inside generated_by since future STT (Speech-to-Text) integrations might give one or the other. 

