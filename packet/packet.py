import copy
from functools import lru_cache

from packet.ldap import ldap_get_member, ldap_is_intromember
from .models import Freshman, UpperSignature, FreshSignature, MiscSignature, db


def sign(signer_username, freshman_username):
    if signer_username == freshman_username:
        return False

    freshman_signed = Freshman.query.filter_by(rit_username=freshman_username).first()
    if freshman_signed is None:
        return False
    packet = freshman_signed.current_packet()
    if packet is None or not packet.is_open():
        return False

    upper_signature = UpperSignature.query.filter(UpperSignature.member == signer_username,
                                                  UpperSignature.packet == packet).first()
    fresh_signature = FreshSignature.query.filter(FreshSignature.freshman_username == signer_username,
                                                  FreshSignature.packet == packet).first()

    if upper_signature:
        if ldap_is_intromember(ldap_get_member(signer_username)):
            return False
        upper_signature.signed = True
    elif fresh_signature:
        # Make sure only on floor freshmen can sign packets
        freshman_signer = Freshman.query.filter_by(rit_username=signer_username).first()
        if freshman_signer and not freshman_signer.onfloor:
            return False
        fresh_signature.signed = True
    else:
        db.session.add(MiscSignature(packet=packet, member=signer_username))
    db.session.commit()

    # Clear functions that read signatures cache
    get_number_signed.cache_clear()
    get_signatures.cache_clear()
    get_upperclassmen_percent.cache_clear()

    return True


@lru_cache(maxsize=2048)
def get_signatures(freshman_username):
    packet = Freshman.query.filter_by(rit_username=freshman_username).first().current_packet()
    eboard = UpperSignature.query.filter_by(packet_id=packet.id, eboard=True).order_by(UpperSignature.signed.desc())
    upper_signatures = UpperSignature.query.filter_by(packet_id=packet.id, eboard=False).order_by(
        UpperSignature.signed.desc())
    fresh_signatures = FreshSignature.query.filter_by(packet_id=packet.id).order_by(FreshSignature.signed.desc())
    misc_signatures = MiscSignature.query.filter_by(packet_id=packet.id)
    return {'eboard': eboard,
            'upperclassmen': upper_signatures,
            'freshmen': fresh_signatures,
            'misc': misc_signatures}


@lru_cache(maxsize=2048)
def get_number_signed(freshman_username):
    return Freshman.query.filter_by(rit_username=freshman_username).first().current_packet().signatures_received()


@lru_cache(maxsize=4096)
def get_number_required(freshman_username):
    return Freshman.query.filter_by(rit_username=freshman_username).first().current_packet().signatures_required()


@lru_cache(maxsize=2048)
def get_upperclassmen_percent(uid):
    upperclassmen_required = copy.deepcopy(get_number_required(uid))
    del upperclassmen_required['freshmen']
    upperclassmen_required = sum(upperclassmen_required.values())

    upperclassmen_signature = copy.deepcopy(get_number_signed(uid))
    del upperclassmen_signature['freshmen']
    upperclassmen_signature = sum(upperclassmen_signature.values())

    return upperclassmen_signature / upperclassmen_required * 100
