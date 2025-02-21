import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function UserDashboard() {
    const [user, setUser] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        const storedUser = localStorage.getItem("user");
        if (!storedUser) {
            navigate("/login"); // Redirect if not logged in
        } else {
            setUser(JSON.parse(storedUser));
        }
    }, [navigate]);

    return (
        <div>
            <h2>User Dashboard</h2>
            {user ? <p>Welcome, {user.username}!</p> : <p>Loading...</p>}
            <button onClick={() => {
                localStorage.removeItem("user"); 
                navigate("/login");
            }}>Logout</button>
        </div>
    );
}

export default UserDashboard;
