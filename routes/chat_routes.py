from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import and_, or_

from extensions import db
from models.user import User
from models.chat import Conversation, Message
from models.notification import Notification


chat_bp = Blueprint("chat", __name__)


# =========================================================
# TEMPORARY TYPING STATE
# =========================================================

typing_users = {}

TYPING_TIMEOUT_SECONDS = 4


# =========================================================
# GET USERS
# =========================================================

@chat_bp.route("/users", methods=["GET"])
@jwt_required()
def get_chat_users():

    current_user_id = int(get_jwt_identity())

    users = (
        User.query
        .filter(User.id != current_user_id)
        .order_by(User.id.asc())
        .all()
    )

    result = []

    for user in users:

        if user.role == "admin":
            full_name = "Admin"
        elif user.employee:
            full_name = (
                f"{user.employee.first_name} "
                f"{user.employee.last_name}"
                ).strip()
        else:
            full_name = user.email

        result.append({

            "id": user.id,

            "name": full_name,

            "email": user.email,

            "role": user.role

        })

    return jsonify(result), 200

# =========================================================
# GET CONVERSATIONS
# =========================================================

@chat_bp.route("/conversations", methods=["GET"])
@jwt_required()
def get_conversations():

    current_user_id = int(get_jwt_identity())

    conversations = (
        Conversation.query
        .filter(
            or_(
                Conversation.user_one_id == current_user_id,
                Conversation.user_two_id == current_user_id
            )
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    result = []

    for conversation in conversations:

        if conversation.user_one_id == current_user_id:
            other_user_id = conversation.user_two_id
        else:
            other_user_id = conversation.user_one_id

        other_user = User.query.get(other_user_id)

        last_message = (
            Message.query
            .filter(
                Message.conversation_id == conversation.id
            )
            .order_by(Message.created_at.desc())
            .first()
        )

        unread_count = (
            Message.query
            .filter(
                Message.conversation_id == conversation.id,
                Message.sender_id != current_user_id,
                Message.is_read == False
            )
            .count()
        )

        # ---------------------------------------------------------
        # GET OTHER USER NAME
        # ---------------------------------------------------------

        if other_user:
            if other_user.role == "admin":
                full_name = "Admin"
            elif other_user.employee:
                full_name = (
                    f"{other_user.employee.first_name} "
                    f"{other_user.employee.last_name}"
                ).strip()
            else:
                full_name = other_user.email
        else:
            full_name = None

        # ---------------------------------------------------------
        # BUILD CONVERSATION RESPONSE
        # ---------------------------------------------------------

        result.append({

            "conversation_id": conversation.id,

            "user": {

                "id": other_user.id,

                "name": full_name,

                "email": other_user.email,

                "role": other_user.role

            } if other_user else None,

            "last_message": (
                last_message.message
                if last_message
                else None
            ),

            "last_message_time": (
                last_message.created_at.isoformat()
                if last_message
                else None
            ),

            "unread_count": unread_count

        })

    # IMPORTANT: this must be outside the for loop
    return jsonify(result), 200

# =========================================================
# CREATE CONVERSATION
# =========================================================

@chat_bp.route("/conversations", methods=["POST"])
@jwt_required()
def create_conversation():

    current_user_id = int(get_jwt_identity())

    data = request.get_json()

    if not data:
        return jsonify({
            "message": "Request body is required"
        }), 400

    other_user_id = data.get("user_id")

    if not other_user_id:
        return jsonify({
            "message": "user_id is required"
        }), 400

    try:
        other_user_id = int(other_user_id)

    except (TypeError, ValueError):
        return jsonify({
            "message": "user_id must be a valid integer"
        }), 400

    if other_user_id == current_user_id:
        return jsonify({
            "message": "You cannot create a conversation with yourself"
        }), 400

    other_user = User.query.get(other_user_id)

    if not other_user:
        return jsonify({
            "message": "User not found"
        }), 404

    conversation = (
        Conversation.query
        .filter(
            or_(
                and_(
                    Conversation.user_one_id == current_user_id,
                    Conversation.user_two_id == other_user_id
                ),
                and_(
                    Conversation.user_one_id == other_user_id,
                    Conversation.user_two_id == current_user_id
                )
            )
        )
        .first()
    )

    if conversation:

        return jsonify({
            "message": "Conversation already exists",
            "conversation_id": conversation.id
        }), 200

    now = datetime.utcnow()

    conversation = Conversation(
        user_one_id=current_user_id,
        user_two_id=other_user_id,
        created_at=now,
        updated_at=now
    )

    db.session.add(conversation)
    db.session.commit()

    return jsonify({
        "message": "Conversation created",
        "conversation_id": conversation.id
    }), 201


# =========================================================
# GET MESSAGES
# =========================================================

@chat_bp.route(
    "/conversations/<int:conversation_id>/messages",
    methods=["GET"]
)
@jwt_required()
def get_messages(conversation_id):

    current_user_id = int(get_jwt_identity())

    conversation = Conversation.query.get(conversation_id)

    if not conversation:
        return jsonify({
            "message": "Conversation not found"
        }), 404

    if (
        conversation.user_one_id != current_user_id
        and conversation.user_two_id != current_user_id
    ):
        return jsonify({
            "message": "You are not allowed to access this conversation"
        }), 403

    messages = (
        Message.query
        .filter(
            Message.conversation_id == conversation_id
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    result = []

    for message in messages:

        result.append({
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "message": message.message,
            "is_read": message.is_read,
            "created_at": message.created_at.isoformat()
        })

    return jsonify(result), 200


@chat_bp.route(
    "/conversations/<int:conversation_id>/messages",
    methods=["POST"]
)
@jwt_required()
def send_message(conversation_id):
    current_user_id = int(get_jwt_identity())

    conversation = Conversation.query.get(conversation_id)

    if not conversation:
        return jsonify({
            "message": "Conversation not found"
        }), 404

    if (
        conversation.user_one_id != current_user_id
        and conversation.user_two_id != current_user_id
    ):
        return jsonify({
            "message": (
                "You are not allowed to send messages "
                "in this conversation"
            )
        }), 403

    data = request.get_json(silent=True) or {}

    message_text = data.get("message")

    if not message_text:
        return jsonify({
            "message": "Message is required"
        }), 400

    message_text = str(message_text).strip()

    if not message_text:
        return jsonify({
            "message": "Message cannot be empty"
        }), 400

    if len(message_text) > 5000:
        return jsonify({
            "message": "Message cannot exceed 5000 characters"
        }), 400

    # -----------------------------------------
    # FIND THE RECIPIENT
    # -----------------------------------------

    if conversation.user_one_id == current_user_id:
        recipient_user_id = conversation.user_two_id
    else:
        recipient_user_id = conversation.user_one_id

    recipient_user = db.session.get(
        User,
        recipient_user_id
    )

    if not recipient_user:
        return jsonify({
            "message": "Recipient user not found"
        }), 404

    # -----------------------------------------
    # FIND THE SENDER'S DISPLAY NAME
    # -----------------------------------------

    sender_user = db.session.get(
        User,
        current_user_id
    )

    if not sender_user:
        return jsonify({
            "message": "Sender user not found"
        }), 404

    if sender_user.role == "admin":
        sender_name = "Admin"

    elif sender_user.employee:
        sender_name = (
            f"{sender_user.employee.first_name} "
            f"{sender_user.employee.last_name}"
        ).strip()

    else:
        sender_name = sender_user.email

    # -----------------------------------------
    # CREATE CHAT MESSAGE
    # -----------------------------------------

    now = datetime.utcnow()

    new_message = Message(
        conversation_id=conversation_id,
        sender_id=current_user_id,
        message=message_text,
        is_read=False,
        created_at=now
    )

    conversation.updated_at = now

    db.session.add(new_message)

    # -----------------------------------------
    # CREATE NOTIFICATION FOR RECIPIENT
    # -----------------------------------------

    chat_notification = Notification(
        employee_id=(
            recipient_user.employee.id
            if recipient_user.employee
            else None
        ),
        user_id=recipient_user.id,
        title="New Message",
        message=f"{sender_name} sent you a message.",
        notification_type="chat_message",
        is_read=False
    )

    db.session.add(chat_notification)

    # -----------------------------------------
    # SAVE BOTH TO DATABASE
    # -----------------------------------------

    try:
        db.session.commit()

    except Exception as exc:
        db.session.rollback()

        print("CHAT NOTIFICATION ERROR:", exc)

        return jsonify({
            "message": "Could not send message",
            "error": str(exc)
        }), 500

    # Stop typing indicator
    typing_users.pop(
        (conversation_id, current_user_id),
        None
    )

    return jsonify({
        "message": "Message sent",
        "data": {
            "id": new_message.id,
            "conversation_id": new_message.conversation_id,
            "sender_id": new_message.sender_id,
            "message": new_message.message,
            "is_read": new_message.is_read,
            "created_at": new_message.created_at.isoformat()
        }
    }), 201


# =========================================================
# MARK MESSAGES AS READ
# =========================================================

@chat_bp.route(
    "/conversations/<int:conversation_id>/read",
    methods=["PATCH"]
)
@jwt_required()
def mark_messages_as_read(conversation_id):

    current_user_id = int(get_jwt_identity())

    conversation = Conversation.query.get(conversation_id)

    if not conversation:
        return jsonify({
            "message": "Conversation not found"
        }), 404

    if (
        conversation.user_one_id != current_user_id
        and conversation.user_two_id != current_user_id
    ):
        return jsonify({
            "message": "You are not allowed to access this conversation"
        }), 403

    messages = (
        Message.query
        .filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user_id,
            Message.is_read == False
        )
        .all()
    )

    for message in messages:
        message.is_read = True

    db.session.commit()

    return jsonify({
        "message": "Messages marked as read",
        "updated_count": len(messages)
    }), 200


# =========================================================
# UPDATE TYPING STATUS
# =========================================================

@chat_bp.route(
    "/conversations/<int:conversation_id>/typing",
    methods=["POST"]
)
@jwt_required()
def update_typing_status(conversation_id):

    current_user_id = int(get_jwt_identity())

    conversation = Conversation.query.get(conversation_id)

    if not conversation:
        return jsonify({
            "message": "Conversation not found"
        }), 404

    if (
        conversation.user_one_id != current_user_id
        and conversation.user_two_id != current_user_id
    ):
        return jsonify({
            "message": "You are not allowed to access this conversation"
        }), 403

    data = request.get_json(silent=True) or {}

    is_typing = bool(
        data.get("is_typing", False)
    )

    typing_key = (
        conversation_id,
        current_user_id
    )

    if is_typing:

        typing_users[typing_key] = (
            datetime.utcnow()
            + timedelta(
                seconds=TYPING_TIMEOUT_SECONDS
            )
        )

    else:

        typing_users.pop(
            typing_key,
            None
        )

    return jsonify({
        "message": "Typing status updated"
    }), 200


# =========================================================
# GET OTHER USER TYPING STATUS
# =========================================================

@chat_bp.route(
    "/conversations/<int:conversation_id>/typing",
    methods=["GET"]
)
@jwt_required()
def get_typing_status(conversation_id):

    current_user_id = int(get_jwt_identity())

    conversation = Conversation.query.get(conversation_id)

    if not conversation:
        return jsonify({
            "message": "Conversation not found"
        }), 404

    if (
        conversation.user_one_id != current_user_id
        and conversation.user_two_id != current_user_id
    ):
        return jsonify({
            "message": "You are not allowed to access this conversation"
        }), 403

    if conversation.user_one_id == current_user_id:
        other_user_id = conversation.user_two_id
    else:
        other_user_id = conversation.user_one_id

    typing_key = (
        conversation_id,
        other_user_id
    )

    typing_until = typing_users.get(typing_key)

    if not typing_until:

        return jsonify({
            "is_typing": False
        }), 200

    if datetime.utcnow() >= typing_until:

        typing_users.pop(
            typing_key,
            None
        )

        return jsonify({
            "is_typing": False
        }), 200

    return jsonify({
        "is_typing": True
    }), 200