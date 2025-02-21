import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser } from "../services/api";

function Login() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [errorMessage, setErrorMessage] = useState("");
    const navigate = useNavigate();  // Redirect after login

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const data = await loginUser({ username, password });
            localStorage.setItem("user", JSON.stringify(data));  // Store user data
            navigate("/dashboard");  // Redirect to dashboard
        } catch (error) {
            setErrorMessage("Invalid credentials. Try again.");
        }
    };

    return (
        <div>
            <h2>Login</h2>
            <form onSubmit={handleSubmit}>
                <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
                <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                <button type="submit">Login</button>
            </form>
            {errorMessage && <p style={{ color: "red" }}>{errorMessage}</p>}
        </div>
    );
}

export default Login;