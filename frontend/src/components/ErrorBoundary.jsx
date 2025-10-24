import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // You can log error here if desired
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ padding: 16 }}>
          <div className="down" style={{ marginBottom: 8 }}>This tab failed to load.</div>
          <button className="btn" onClick={() => this.setState({ hasError: false, error: null })}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}

