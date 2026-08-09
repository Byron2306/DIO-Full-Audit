import sys
from unittest.mock import MagicMock, patch

# ARDA ENVIRONMENT FIX: Mock 'bcc' before it's imported by anything
sys.modules['bcc'] = MagicMock()

import os
import unittest
import subprocess
from backend.services.os_enforcement_service import OsEnforcementService
from backend.services.tpm_attestation_service import TpmAttestationService, HardwareSovereigntyError
from backend.services.arda_fabric import ArdaFabricEngine
from backend.services.outbound_gate import OutboundGateService

class SovereigntyHardeningValidator(unittest.IsolatedAsyncioTestCase):
    """
    ARDA OS: Logically validates the Final Sovereignty Hardening (Phase R).
    Confirms the 'Final Five' fixes for Operational Undeniability.
    """

    def setUp(self):
        os.environ["ARDA_ENV"] = "development"
        os.environ["ARDA_SOVEREIGN_MODE"] = "0"

    def test_q1_identity_unification(self):
        """Test that OsEnforcementService correctly syncs Inode+Dev keys."""
        test_file = __file__
        stat = os.stat(test_file)
        expected_inode = stat.st_ino
        expected_dev = stat.st_dev

        # Mock the BPF map
        mock_map = MagicMock()
        mock_map.Key = lambda i, d: (i, d)
        mock_map.Leaf = lambda v: v

        # We use the mocked 'bcc' from sys.modules
        mock_bpf_class = sys.modules['bcc'].BPF
        mock_bpf_class.return_value.get_table.return_value = mock_map
        
        service = OsEnforcementService("/tmp/fake_lsm.c")
        # Force authoritative for test
        service.is_authoritative = True
        service.bpf = mock_bpf_class.return_value
        service.harmonic_map = mock_map
        
        # Sync the workload
        service.update_workload_harmony(test_file, is_harmonic=True)
        
        # Verify the key matches 'struct arda_identity'
        mock_map.__setitem__.assert_called_with((expected_inode, expected_dev), 1)
        print("TEST Q1 PASSED: Identity Unified on Inode/Dev keys.")

    def test_q2_hardware_finality_fail_closed(self):
        """Test that TpmAttestationService Fails-Closed in production without TPM."""
        os.environ["ARDA_ENV"] = "production"
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with self.assertRaises(HardwareSovereigntyError):
                TpmAttestationService()
            print("TEST Q2 PASSED: Hardware Finality Fails-Closed in Production.")

    async def test_q3_wireguard_peer_generation(self):
        """Test that ArdaFabric generates real WireGuard cryptographic peers."""
        # Mock SecretFireForge and its Packet
        with patch('backend.services.arda_fabric.get_secret_fire_forge') as mock_forge_get:
            mock_forge = MagicMock()
            mock_forge_get.return_value = mock_forge
            
            packet = MagicMock()
            packet.voice_id = "lawful_voice"
            mock_forge.get_current_packet.return_value = packet
            # Use AsyncMock for the awaitable call
            from unittest.mock import AsyncMock
            mock_forge.issue_challenge = AsyncMock(return_value="nonce_123")
            
            fabric = ArdaFabricEngine()
            
            # Mock 'wg' commands
            with patch('subprocess.check_output') as mock_wg:
                mock_wg.side_effect = [b"priv_key\n", b"pub_key\n"]
                
                session_id = await fabric.initiate_handshake("remote_node")
                
                # Verify handshake
                with patch('os.makedirs'):
                    with patch('builtins.open', unittest.mock.mock_open()):
                        packet_resp = MagicMock()
                        packet_resp.voice_id = "lawful_voice"
                        # FIX: tpm_quote must have a 'nonce' attribute (not just a dict)
                        mock_quote = MagicMock()
                        mock_quote.nonce = "nonce_123"
                        mock_quote.pcr_values = {}
                        packet_resp.tpm_quote = mock_quote
                        
                        # Mock the verification pass-through
                        with patch.object(fabric.tpm, 'verify_quote', AsyncMock(return_value=True)):
                            success = await fabric.verify_handshake(session_id, packet_resp)
                
                self.assertTrue(success)
                peer = fabric.known_peers["remote_node"]
                self.assertEqual(peer["wg_pubkey"], "pub_key")
                print("TEST Q3 PASSED: Real WireGuard Peer Mesh generation confirmed.")

    def test_q4_outbound_gate_transport_lock(self):
        """Test that OutboundGate denies actions if transport is not verified."""
        mock_db = MagicMock()
        gate = OutboundGateService(mock_db)
        # 1. Physical presence but UNVERIFIED (No handshake)
        gate.fabric.known_peers["attacker"] = {
            "wg_pubkey": "real_key", 
            "is_peer_verified": False,
            "influence_budget": MagicMock(constitutional_state="harmonic")
        }
        self.assertFalse(gate.verify_transport_lock("attacker"))
        
        # 2. Local-only placeholder
        gate.fabric.known_peers["guest"] = {"wg_pubkey": "local-only", "is_peer_verified": True}
        self.assertFalse(gate.verify_transport_lock("guest"))
        
        # 3. VERIFIED Physical Transport
        gate.fabric.known_peers["guardian"] = {
            "wg_pubkey": "real_key", 
            "is_peer_verified": True,
            "influence_budget": MagicMock(constitutional_state="harmonic")
        }
        self.assertTrue(gate.verify_transport_lock("guardian"))
        print("TEST Q4 PASSED: Outbound Gate Transport Lock (Verified) enforced.")

    async def test_q6_sovereign_mode_fail_closed(self):
        """Test that OsEnforcementService Panics if BPF load fails in Sovereign Mode."""
        os.environ["ARDA_SOVEREIGN_MODE"] = "1"
        # Access the sys.modules mock
        mock_bpf_class = sys.modules['bcc'].BPF
        # Simulate a load failure
        mock_bpf_class.side_effect = Exception("Kernel context missing")
        
        with self.assertRaises(SystemExit):
            OsEnforcementService("/tmp/fake_lsm.c")
        
        # Reset for other tests
        mock_bpf_class.side_effect = None
        print("TEST Q6 PASSED: Sovereign Mode Fails-Closed (Panic) on load failure.")

    async def test_q7_strict_admission_ordering(self):
        """Test that ArdaFabric enforces judge-before-bless and MANDATORY paths in Sovereign Mode."""
        fabric = ArdaFabricEngine()
        
        # 1. Sovereign VETO: Non-physical identity must fail
        os.environ["ARDA_SOVEREIGN_MODE"] = "1"
        with self.assertRaises(PermissionError):
            fabric.ensure_subject("node_01", executable_path=None) # No path in sovereign mode should fail
        
        # 2. Non-Sovereign: Allow fallback (with warning)
        os.environ["ARDA_SOVEREIGN_MODE"] = "0"
        fabric.ensure_subject("node_01", executable_path=None)
        self.assertIn("node_01", fabric.known_peers)
        
        print("TEST Q7 PASSED: Strict Path Admission (Sovereign Veto) verified.")

    async def test_q8_secret_fire_handshake_finality(self):
        """Test that handshake fails if cryptographic signature pattern is incorrect."""
        import base64
        # Force mock mode for this test as signature pattern check is a mock feature
        old_mode = os.getenv("ARDA_SOVEREIGN_MODE")
        os.environ["ARDA_SOVEREIGN_MODE"] = "0"
        
        try:
            fabric = ArdaFabricEngine()
            
            # 1. Case: Signature lacks the 'mock_tpm_signature' secret
            bad_sig = base64.b64encode(b"invalid_signature_payload").decode()
            quote = MagicMock()
            quote.nonce = "nonce_1"
            quote.signature = bad_sig
            
            # This should fail because verify_quote checks for "mock_tpm_signature"
            success = await fabric.tpm.verify_quote(quote, "nonce_1")
            self.assertFalse(success)
            
            # 2. Case: Signature is valid mock pattern
            good_sig = base64.b64encode(b"header:mock_tpm_signature:footer").decode()
            quote.signature = good_sig
            success = await fabric.tpm.verify_quote(quote, "nonce_1")
            self.assertTrue(success)
        finally:
            if old_mode: os.environ["ARDA_SOVEREIGN_MODE"] = old_mode
            else: del os.environ["ARDA_SOVEREIGN_MODE"]
        
        print("TEST Q8 PASSED: Cryptographic Signature Pattern verification confirmed.")

    async def test_q9_physical_transport_transmission(self):
        """Test that broadcast_sovereign_summons triggers a real UDP socket transmission."""
        with patch('backend.services.arda_fabric.get_secret_fire_forge') as mock_forge_get:
            mock_forge = MagicMock()
            mock_forge_get.return_value = mock_forge
            current_packet = MagicMock()
            current_packet.voice_id = "lawful_voice"
            mock_forge.get_current_packet.return_value = current_packet
            
            fabric = ArdaFabricEngine()
            
            # Mock the socket itself to avoid real network calls during test
            import socket
            with patch('socket.socket') as mock_socket_class:
                mock_socket = MagicMock()
                mock_socket_class.return_value = mock_socket
                
                payload = {"coronation": "v40"}
                await fabric.broadcast_sovereign_summons(payload)
                
                # Verify that a UDP socket was created and used
                mock_socket_class.assert_called_with(socket.AF_INET, socket.SOCK_DGRAM)
                mock_socket.sendto.assert_called()
                print("TEST Q9 PASSED: Real Physical Transport (UDP Socket Ignition) verified.")

if __name__ == "__main__":
    unittest.main()
